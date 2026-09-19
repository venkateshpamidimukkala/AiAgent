import json
import re

import httpx
from fastapi import HTTPException

from .config import settings


def draft_reply(sender: str, subject: str, body: str, instruction: str) -> str:
    if settings.openai_api_key:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = f"Write a concise professional reply. Request: {instruction}\nFrom: {sender}\nSubject: {subject}\nMessage: {body}"
        return client.chat.completions.create(model=settings.openai_model, messages=[{"role":"user","content":prompt}]).choices[0].message.content or ""
    return f"Hi {sender.split('@')[0]},\n\nThanks for your message regarding \"{subject}\". I will review this and follow up shortly.\n\nBest regards"


def revise(text: str, instruction: str) -> str:
    if "formal" in instruction.lower():
        return text.replace("Hi ", "Dear ").replace("Thanks", "Thank you")
    if "short" in instruction.lower():
        return text.split("\n\n")[0] + "\n\nI will follow up shortly."
    return text + f"\n\n[Revision requested: {instruction}]"


def answer_confluence(question: str, page: dict[str, str], focus: str = "everything") -> dict[str, str | list[str]]:
    content = page.get("content", "")
    if settings.openai_api_key:
        from openai import OpenAI
        prompt = ("Answer only from the Confluence content below. Do not invent facts. "
                  "Return valid JSON with exactly these keys: answer (string), summary (string), "
                  "key_points (array of strings), problems (array of strings), implementation (array of strings). "
                  "The user wants this focus: " + focus + ". If a section is not covered, return an empty array or say that it is not specified.\n\n"
                  f"Page title: {page.get('title')}\nQuestion: {question}\nPage content:\n{content[:30000]}")
        result = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0].message.content or ""
        try:
            value = json.loads(result)
            return {"answer": value.get("answer", ""), "summary": value.get("summary", ""),
                    "key_points": value.get("key_points", []), "problems": value.get("problems", []),
                    "implementation": value.get("implementation", [])}
        except (json.JSONDecodeError, TypeError):
            return {"answer": result or "I could not find an answer on this page.", "summary": result,
                    "key_points": [], "problems": [], "implementation": []}
    paragraphs = [item.strip() for item in content.split("\n\n") if item.strip()]
    if not paragraphs:
        empty = "This Confluence page does not contain readable text."
        return {"answer": empty, "summary": empty, "key_points": [], "problems": [], "implementation": []}
    summary = " ".join(paragraphs[:2])[:600]
    key_points = [item[:240] for item in paragraphs[:5]]
    problem_terms = ("problem", "risk", "block", "issue", "challenge", " limitation", "error")
    implementation_terms = ("implement", "step", "configure", "install", "deploy", "use", "setup")
    problems = [item[:240] for item in paragraphs if any(term in item.lower() for term in problem_terms)][:5]
    implementation = [item[:240] for item in paragraphs if any(term in item.lower() for term in implementation_terms)][:5]
    terms = [term.lower() for term in re.findall(r"[a-zA-Z]{4,}", question)]
    matches = [item for item in paragraphs if any(term in item.lower() for term in terms)]
    answer = "\n\n".join(matches[:3]) if matches else summary
    return {"answer": answer, "summary": summary, "key_points": key_points,
            "problems": problems or ["No specific problems or risks were mentioned on this page."],
            "implementation": implementation or ["The page does not specify implementation steps for this request."]}


def translate_for_voice(text: str, language: str) -> str:
    requested_language = language.strip().lower()
    if requested_language.startswith("en"):
        return text
    target = requested_language.split("-", 1)[0]
    if not settings.google_translate_api_key and not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Translation is not configured. Add GOOGLE_TRANSLATE_API_KEY to backend/.env and restart the backend.")
    if settings.google_translate_api_key:
        response = httpx.post(
            "https://translation.googleapis.com/language/translate/v2",
            params={"key": settings.google_translate_api_key},
            json={"q": text[:30000], "target": target, "format": "text"},
            timeout=30.0,
        )
        response.raise_for_status()
        translated = response.json().get("data", {}).get("translations", [{}])[0].get("translatedText")
        if translated:
            return translated
    if settings.openai_api_key:
        from openai import OpenAI
        result = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": f"Translate the following work notification into {target}. Preserve names, product names, URLs, and meaning. Return only the translation."}, {"role": "user", "content": text[:30000]}],
        )
        translated = result.choices[0].message.content
        if translated:
            return translated
    raise HTTPException(status_code=502, detail=f"The translation provider returned no translation for language '{target}'.")


def answer_workspace(query: str, messages: list[dict[str, str]]) -> str:
    context = "\n".join(f"- {item['subject']} ({item['source']}): {item['body']}" for item in messages)
    if settings.openai_api_key:
        from openai import OpenAI
        prompt = ("You are an enterprise work assistant. Answer the user's request using the workspace context. "
                  "Be concise, actionable, and transparent when context is insufficient.\n\n"
                  f"User request: {query}\nWorkspace context:\n{context or 'No matching workspace items.'}")
        result = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return result.choices[0].message.content or "I could not generate a response."
    if not messages:
        return (f"I received your request: “{query}”. Connect Outlook, Teams, Jira, or Confluence to give me workspace context, "
                "or configure OPENAI_API_KEY for broader assistant answers.")
    if any(word in query.lower() for word in ("summar", "review", "priorit", "important", "decision")):
        return "Here are the highest-priority items I found:\n" + "\n".join(
            f"• {item['subject']} — {item['body'][:180]}" for item in messages[:5]
        )
    return f"I found {len(messages)} relevant workspace item(s):\n" + "\n".join(f"• {item['subject']} ({item['source']})" for item in messages[:5])
