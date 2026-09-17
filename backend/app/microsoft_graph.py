from datetime import datetime, timedelta, timezone
import re
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .models import Message, OAuthToken
from .priority import score

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def _text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"<[^>]+>", " ",
                  value).replace("&nbsp;", " ").strip()


def _sender(item: dict[str, Any]) -> str:
    sender = item.get("from") or item.get("sender") or {}
    user = sender.get("user") or sender.get("emailAddress") or {}
    return user.get("email") or user.get("address") or user.get("displayName") or "Unknown sender"


def _date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _upsert(db: Session, source: str, item: dict[str, Any], subject: str, body: str, thread_id: str | None = None) -> bool:
    external_id = f"microsoft:{source}:{item.get('id')}"
    if not item.get("id") or db.scalar(select(Message.id).where(Message.external_id == external_id)):
        return False
    sender = _sender(item)
    value, label = score(sender, subject, body)
    db.add(Message(source=source, external_id=external_id, sender=sender, subject=subject or "(No subject)", body=body or "(No message body)", thread_id=thread_id, priority_score=value, priority_label=label, created_at=_date(item.get("receivedDateTime") or item.get("createdDateTime"))))
    return True


def _get(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    response = client.get(f"{GRAPH_ROOT}{path}", params=params)
    response.raise_for_status()
    return response.json().get("value", [])


def outlook_summary(db: Session) -> dict[str, int]:
    """Return the small Outlook dashboard counters for the connected account."""
    token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    if not token:
        return {"unread_emails": 0, "upcoming_meetings": 0}

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=30)
    headers = {"Authorization": f"Bearer {token.access_token}"}
    try:
        with httpx.Client(headers={**headers, "ConsistencyLevel": "eventual"}, timeout=20) as client:
            meetings = _get(client, "/me/calendarView", {
                "startDateTime": now.isoformat(),
                "endDateTime": end.isoformat(),
                "$top": 100,
                "$select": "id",
                "$orderby": "start/dateTime",
            })
            # Graph may cap the returned list; the dashboard only needs a
            # useful count and the endpoint's @odata.count when available.
            unread_response = client.get(f"{GRAPH_ROOT}/me/mailFolders/inbox/messages", params={
                "$filter": "isRead eq false", "$top": 1, "$count": "true", "$select": "id",
            })
            unread_response.raise_for_status()
            unread_count = int(unread_response.json().get("@odata.count", len(unread_response.json().get("value", []))))
            return {"unread_emails": unread_count, "upcoming_meetings": len(meetings)}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Microsoft Graph access expired or Calendars.Read permission is missing.") from exc
        raise RuntimeError(f"Microsoft Graph request failed with HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Microsoft Graph is temporarily unavailable.") from exc


def sync_microsoft_messages(db: Session) -> dict[str, int]:
    token = db.scalar(select(OAuthToken).where(OAuthToken.provider == "microsoft"))
    if not token:
        return {"outlook": 0, "teams": 0}
    headers = {"Authorization": f"Bearer {token.access_token}"}
    added = {"outlook": 0, "teams": 0}
    requested_scopes = set(settings.microsoft_scopes.split())
    try:
        with httpx.Client(headers=headers, timeout=20) as client:
            mail = _get(client, "/me/mailFolders/inbox/messages", {"$top": 25, "$select": "id,subject,body,from,receivedDateTime,conversationId", "$orderby": "receivedDateTime desc"})
            for item in mail:
                content = item.get("body", {}).get("content", "")
                if _upsert(db, "outlook", item, item.get("subject", ""), _text(content), item.get("conversationId")):
                    added["outlook"] += 1
            if {"Chat.Read", "ChannelMessage.Read.All", "Team.ReadBasic.All"}.issubset(requested_scopes):
                chats = _get(client, "/me/chats/getAllMessages", {"$top": 50})
                for item in chats:
                    body = _text((item.get("body") or {}).get("content", ""))
                    if _upsert(db, "teams", item, "Teams chat", body, item.get("chatId")):
                        added["teams"] += 1
                teams = _get(client, "/me/joinedTeams", {"$top": 20})
                for team in teams:
                    channels = _get(client, f"/teams/{team['id']}/channels", {"$top": 20})
                    for channel in channels:
                        messages = _get(client, f"/teams/{team['id']}/channels/{channel['id']}/messages", {"$top": 25})
                        for item in messages:
                            body = _text((item.get("body") or {}).get("content", ""))
                            if _upsert(db, "teams", item, f"{team.get('displayName', 'Team')} · {channel.get('displayName', 'Channel')}", body, channel.get("id")):
                                added["teams"] += 1
        db.commit()
        return added
    except httpx.HTTPStatusError as exc:
        db.rollback()
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Microsoft Graph access expired or permissions are missing.") from exc
        raise RuntimeError(f"Microsoft Graph request failed with HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        db.rollback()
        raise RuntimeError("Microsoft Graph is temporarily unavailable.") from exc
