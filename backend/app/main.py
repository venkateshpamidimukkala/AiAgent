from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session
from .ai import answer_confluence, answer_workspace, draft_reply, revise, translate_for_voice
from .confluence import configure as configure_confluence, disconnect as disconnect_confluence, fetch_page, restore as restore_confluence, search_pages, status as confluence_status
from .config import settings
from .db import Base, engine, get_db
from .models import AssistantRequest, DraftReply, Message, OAuthToken
from .microsoft_auth import authorization_url, configured, exchange_code, token_expiry
from .microsoft_graph import outlook_summary, sync_microsoft_messages
from .jira import add_comment, configure as configure_jira, disconnect as disconnect_jira, restore as restore_jira, search_issues, status as jira_status
from .priority import score
from .providers import dispatch_provider
from .schemas import AssistantQueryOut, AssistantQueryRequest, AssistantRequestOut, ConfluenceAskRequest, ConfluenceConnect, ConfluencePageRequest, DraftCreate, DraftOut, JiraCommentRequest, JiraConnect, JiraSearchRequest, MessageOut, ReviseRequest, VoiceTranslateRequest


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with next(get_db()) as db:
        restore_jira(db)
        restore_confluence(db)
        if not db.scalar(select(Message.id).limit(1)):
            rows = [("gmail", "manager@acme.test", "P1: Production release blocker", "The release is blocked and needs a decision today."), ("teams", "client@acme.test", "Urgent: call moved to 3 PM", "Can you confirm attendance for the customer call?"), ("jira", "jira@acme.test", "Update documentation", "Please review the normal-priority documentation task.")]
            for source, sender, subject, body in rows:
                value, label = score(sender, subject, body)
                db.add(Message(source=source, external_id=f"demo-{source}", sender=sender, subject=subject, body=body, priority_score=value, priority_label=label))
            db.commit()
    yield


app = FastAPI(title="Unified Voice Assistant API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "postgresql" if engine.url.drivername.startswith("postgresql") else "non-postgresql"}

@app.get("/api/connections/status")
def connections_status(db: Session = Depends(get_db)):
    """Return integration status and safe database metadata for the connections page."""
    database_type = "postgresql" if engine.url.drivername.startswith("postgresql") else "sqlite" if engine.url.drivername.startswith("sqlite") else engine.url.drivername
    database = {"connected": False, "type": database_type, "name": engine.url.database or "", "schemas": [], "tables": [], "error": None}
    try:
        db.execute(select(1))
        database["connected"] = True
        if database_type == "postgresql":
            database["schemas"] = list(db.scalars(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name")))
            database["tables"] = list(db.scalars(text("SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_schema, table_name")))
        elif database_type == "sqlite":
            database["schemas"] = ["main"]
            database["tables"] = list(db.scalars(text("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")))
    except Exception as exc:
        database["error"] = str(exc)
    microsoft_token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    return {
        "database": database,
        "providers": {
            "microsoft": {"configured": configured(), "connected": microsoft_token is not None, "account_email": microsoft_token.account_email if microsoft_token else None},
            "jira": jira_status(db),
            "confluence": confluence_status(db),
        },
    }

@app.post("/api/assistant/query", response_model=AssistantQueryOut)
def assistant_query(payload: AssistantQueryRequest, db: Session = Depends(get_db)):
    request = AssistantRequest(request_text=payload.query, request_type=payload.request_type)
    db.add(request)
    db.commit()
    db.refresh(request)
    try:
        terms = {word.lower() for word in payload.query.split() if len(word) > 3}
        all_messages = db.scalars(select(Message).order_by(desc(Message.priority_score), desc(Message.created_at)).limit(100)).all()
        matching = [item for item in all_messages if not terms or any(term in f"{item.subject} {item.body}".lower() for term in terms)]
        context = [{"subject": item.subject, "body": item.body, "source": item.source} for item in (matching or all_messages[:5])]
        answer = answer_workspace(payload.query, context)
        request.response_text = answer
        request.status = "completed"
        request.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"id": request.id, "query": payload.query, "answer": answer, "request_type": request.request_type, "status": request.status, "created_at": request.created_at}
    except Exception as exc:
        request.status = "failed"
        request.error_detail = str(exc)
        request.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(500, "Assistant request failed and was recorded in the database.") from exc

@app.get("/api/assistant/requests", response_model=list[AssistantRequestOut])
def assistant_requests(limit: int = 20, db: Session = Depends(get_db)):
    return db.scalars(select(AssistantRequest).order_by(desc(AssistantRequest.created_at)).limit(min(max(limit, 1), 100))).all()

@app.post("/api/voice/translate")
def translate_voice(payload: VoiceTranslateRequest):
    return {"text": translate_for_voice(payload.text, payload.language), "language": payload.language}

@app.get("/api/confluence/status")
def get_confluence_status(db: Session = Depends(get_db)): return confluence_status(db)

@app.post("/api/confluence/connect")
def connect_confluence(payload: ConfluenceConnect, db: Session = Depends(get_db)):
    try:
        configure_confluence(payload.base_url, payload.email, payload.api_token, db)
        return confluence_status(db)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/confluence/disconnect")
def disconnect_confluence_endpoint(db: Session = Depends(get_db)):
    disconnect_confluence(db)
    return {"connected": False}

@app.get("/api/jira/status")
def get_jira_status(db: Session = Depends(get_db)): return jira_status(db)

@app.post("/api/jira/connect")
def connect_jira(payload: JiraConnect, db: Session = Depends(get_db)):
    try:
        configure_jira(payload.base_url, payload.email, payload.api_token, db)
        return jira_status(db)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/jira/disconnect")
def disconnect_jira_endpoint(db: Session = Depends(get_db)):
    disconnect_jira(db)
    return {"connected": False}

@app.post("/api/jira/search")
def jira_search(payload: JiraSearchRequest, db: Session = Depends(get_db)):
    try:
        return {"issues": search_issues(payload.query, db)}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/jira/comment")
def jira_comment(payload: JiraCommentRequest, db: Session = Depends(get_db)):
    try:
        add_comment(payload.issue_key, payload.body, db)
        return {"status": "added"}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/confluence/page")
def confluence_page(payload: ConfluencePageRequest, db: Session = Depends(get_db)):
    try:
        return fetch_page(payload.url, db)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/confluence/ask")
def ask_confluence(payload: ConfluenceAskRequest, db: Session = Depends(get_db)):
    try:
        if payload.url.strip():
            page = fetch_page(payload.url, db)
            return {"answer": answer_confluence(payload.question, page), "source": {"title": page["title"], "url": page["url"]}}
        pages = search_pages(payload.question, db)
        if not pages:
            return {"answer": "I could not find matching Confluence pages for that question.", "source": {"title": "Confluence search", "url": confluence_status(db)["base_url"]}}
        context = {"title": "Confluence workspace search", "url": pages[0]["url"], "content": "\n\n".join(f"{page['title']}\n{page['content']}" for page in pages)}
        return {"answer": answer_confluence(payload.question, context), "source": {"title": pages[0]["title"], "url": pages[0]["url"]}}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get("/api/auth/microsoft/status")
def microsoft_status(db: Session = Depends(get_db)):
    token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    result = {"configured": configured(), "connected": token is not None, "account_email": token.account_email if token else None, "unread_emails": 0, "upcoming_meetings": 0}
    if token:
        try:
            result.update(outlook_summary(db))
        except RuntimeError:
            # Keep connection status usable when Graph counters are temporarily unavailable.
            pass
    return result

@app.get("/api/auth/microsoft/login")
def microsoft_login():
    return RedirectResponse(authorization_url())

@app.get("/api/auth/microsoft/callback")
def microsoft_callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    if error:
        return RedirectResponse(f"{settings.frontend_origin}/?connected=microsoft&error={error}")
    if not code or not state:
        raise HTTPException(400, "Microsoft OAuth callback did not include code and state.")
    result = exchange_code(code, state)
    graph_profile = None
    try:
        import httpx
        graph_profile = httpx.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {result['access_token']}"}, timeout=10).json()
    except Exception:
        graph_profile = {}
    token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    if token is None:
        token = OAuthToken(provider="microsoft")
        db.add(token)
    token.access_token = result["access_token"]
    token.refresh_token = result.get("refresh_token")
    token.expires_at = token_expiry(result)
    token.account_email = graph_profile.get("mail") or graph_profile.get("userPrincipalName")
    db.commit()
    try:
        sync_microsoft_messages(db)
    except RuntimeError:
        pass
    return RedirectResponse(f"{settings.frontend_origin}/?connected=microsoft")

@app.post("/api/auth/microsoft/disconnect")
def microsoft_disconnect(db: Session = Depends(get_db)):
    token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    if token:
        db.delete(token); db.commit()
    return {"connected": False}

@app.get("/api/messages", response_model=list[MessageOut])
def messages(limit: int = 20, db: Session = Depends(get_db)):
    return db.scalars(select(Message).order_by(desc(Message.priority_score), desc(Message.created_at)).limit(min(limit, 100))).all()

@app.post("/api/messages/sync")
def sync_messages(db: Session = Depends(get_db)):
    try:
        counts = sync_microsoft_messages(db)
        return {"status": "ok", "counts": counts}
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.get("/api/messages/{message_id}", response_model=MessageOut)
def message(message_id: int, db: Session = Depends(get_db)):
    item = db.get(Message, message_id)
    if not item: raise HTTPException(404, "Message not found")
    return item

@app.post("/api/replies/draft", response_model=DraftOut)
def create_draft(payload: DraftCreate, db: Session = Depends(get_db)):
    item = db.get(Message, payload.message_id)
    if not item: raise HTTPException(404, "Message not found")
    draft = DraftReply(message_id=item.id, draft_text=draft_reply(item.sender, item.subject, item.body, payload.instruction))
    db.add(draft); db.commit(); db.refresh(draft); return draft

@app.post("/api/replies/{draft_id}/revise", response_model=DraftOut)
def revise_draft(draft_id: int, payload: ReviseRequest, db: Session = Depends(get_db)):
    draft = db.get(DraftReply, draft_id)
    if not draft: raise HTTPException(404, "Draft not found")
    draft.draft_text = revise(draft.draft_text, payload.instruction); db.commit(); db.refresh(draft); return draft

@app.post("/api/replies/{draft_id}/send")
def send_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.get(DraftReply, draft_id)
    if not draft: raise HTTPException(404, "Draft not found")
    item = db.get(Message, draft.message_id)
    result = dispatch_provider.send(item.source, item.sender, item.subject, draft.draft_text)
    draft.status = "sent"; db.commit(); return {"status": "sent", "provider_id": result}

@app.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not settings.openai_api_key: return {"text": "Voice transcription is ready. Configure OPENAI_API_KEY for Whisper."}
    from openai import OpenAI
    result = OpenAI(api_key=settings.openai_api_key).audio.transcriptions.create(model=settings.openai_stt_model, file=(audio.filename, await audio.read(), audio.content_type))
    return {"text": result.text}
