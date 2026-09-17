import re

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


def answer_confluence(question: str, page: dict[str, str]) -> str:
    content = page.get("content", "")
    if settings.openai_api_key:
        from openai import OpenAI
        prompt = ("Answer only from the Confluence page below. If the answer is not present, say so clearly. "
                  "For summaries, use concise bullet points.\n\n"
                  f"Page title: {page.get('title')}\nQuestion: {question}\nPage content:\n{content[:30000]}")
        return OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0].message.content or "I could not find an answer on this page."
    paragraphs = [item.strip() for item in content.split("\n\n") if item.strip()]
    if not paragraphs:
        return "This Confluence page does not contain readable text."
    if any(word in question.lower() for word in ("summar", "main point", "key point", "overview")):
        return "\n".join(f"• {item[:240]}" for item in paragraphs[:5])
    terms = [term.lower() for term in re.findall(r"[a-zA-Z]{4,}", question)]
    matches = [item for item in paragraphs if any(term in item.lower() for term in terms)]
    return ("\n\n".join(matches[:3]) if matches else
            "I could not find that information on this Confluence page. Try asking for a summary or use terms from the page.")


def translate_for_voice(text: str, language: str) -> str:
    if language.lower().startswith("en"):
        return text
    language_names = {"es": "Spanish", "fr": "French", "de": "German", "hi": "Hindi", "te": "Telugu", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "zh": "Chinese"}
    target = language_names.get(language.lower(), language)
    if settings.openai_api_key:
        from openai import OpenAI
        result = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": f"Translate the following work notification into {target}. Preserve names, product names, URLs, and meaning. Return only the translation."}, {"role": "user", "content": text[:30000]}],
        )
        return result.choices[0].message.content or text
    return text


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
