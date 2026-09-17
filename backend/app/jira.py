import base64
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import settings
from .models import IntegrationCredential


_runtime_credentials: dict[str, str] = {}


def restore(db=None) -> bool:
    """Load saved Jira credentials into the process after a backend restart."""
    saved = db.query(IntegrationCredential).filter_by(provider="jira").first() if db is not None else None
    if saved is None:
        return False
    _runtime_credentials.update({
        "base_url": saved.base_url,
        "email": saved.email,
        "api_token": saved.api_token,
    })
    return True


def _site_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid Jira site URL, such as https://company.atlassian.net")
    return f"{parsed.scheme}://{parsed.netloc}"


def configure(base_url: str, email: str, api_token: str, db=None) -> None:
    site_url = _site_url(base_url)
    if not email.strip() or not api_token.strip():
        raise ValueError("Enter the Jira account email and API token.")
    credentials = {"base_url": site_url, "email": email.strip(), "api_token": api_token.strip()}
    _validate(credentials)
    _runtime_credentials.update(credentials)
    if db is not None:
        saved = db.query(IntegrationCredential).filter_by(provider="jira").first()
        if saved is None:
            db.add(IntegrationCredential(provider="jira", **credentials))
        else:
            saved.base_url, saved.email, saved.api_token = credentials.values()
        db.commit()


def disconnect(db=None) -> None:
    _runtime_credentials.clear()
    if db is not None:
        saved = db.query(IntegrationCredential).filter_by(provider="jira").first()
        if saved is not None:
            db.delete(saved)
            db.commit()


def status(db=None) -> dict[str, Any]:
    saved = db.query(IntegrationCredential).filter_by(provider="jira").first() if db is not None else None
    configured = bool(_runtime_credentials or saved or (settings.jira_base_url and settings.jira_email and settings.jira_api_token))
    if saved and not _runtime_credentials:
        _runtime_credentials.update({"base_url": saved.base_url, "email": saved.email, "api_token": saved.api_token})
    values = _runtime_credentials or {
        "base_url": settings.jira_base_url or "",
        "email": settings.jira_email or "",
    }
    return {"configured": configured, "connected": configured, "base_url": values["base_url"], "email": values["email"]}


def _credentials(db=None) -> tuple[str, str, str]:
    saved = db.query(IntegrationCredential).filter_by(provider="jira").first() if db is not None else None
    values = _runtime_credentials or ({"base_url": saved.base_url, "email": saved.email, "api_token": saved.api_token} if saved else {
        "base_url": settings.jira_base_url or "",
        "email": settings.jira_email or "",
        "api_token": settings.jira_api_token or "",
    })
    if not all(values.values()):
        raise RuntimeError("Jira is not configured. Add the site URL, email, and API token.")
    return values["base_url"], values["email"], values["api_token"]


def _headers(email: str, api_token: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}


def _validate(credentials: dict[str, str]) -> None:
    try:
        response = httpx.get(f"{credentials['base_url']}/rest/api/3/myself", headers=_headers(credentials["email"], credentials["api_token"]), timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or account permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while connecting.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable. Check the site URL and network connection.") from exc


def search_issues(query: str, db=None) -> list[dict[str, Any]]:
    base_url, email, api_token = _credentials(db)
    query = query.strip()
    if not query:
        raise ValueError("Enter a Jira issue search or question.")
    escaped = query.replace('"', '\\"')
    jql = f'text ~ "{escaped}" ORDER BY updated DESC'
    params = {"jql": jql, "maxResults": 10, "fields": "summary,description,status,priority,assignee,updated"}
    try:
        # Jira Cloud deprecated /rest/api/3/search in favour of /search/jql.
        # Keep the old endpoint as a compatibility fallback for older Jira
        # Server/Data Center installations.
        response = httpx.get(f"{base_url}/rest/api/3/search/jql", params=params, headers=_headers(email, api_token), timeout=20)
        if response.status_code in (404, 410):
            response = httpx.get(f"{base_url}/rest/api/3/search", params=params, headers=_headers(email, api_token), timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or issue search permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while searching.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable.") from exc
    issues = []
    for item in response.json().get("issues", []):
        fields = item.get("fields") or {}
        issues.append({
            "key": item.get("key", ""),
            "summary": fields.get("summary", "Jira issue"),
            "status": (fields.get("status") or {}).get("name", "Unknown"),
            "priority": (fields.get("priority") or {}).get("name", "Unassigned"),
            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
            "updated": fields.get("updated"),
            "url": f"{base_url}/browse/{item.get('key', '')}",
        })
    return issues


def add_comment(issue_key: str, body: str, db=None) -> None:
    base_url, email, api_token = _credentials(db)
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}}
    try:
        response = httpx.post(f"{base_url}/rest/api/3/issue/{issue_key.strip()}/comment", json=payload, headers={**_headers(email, api_token), "Content-Type": "application/json"}, timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or comment permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while adding the comment.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable.") from exc


def assigned_issues_missing_comment_today(db=None) -> list[dict[str, Any]]:
    """Return assigned issues for the current Jira user without a comment today."""
    base_url, email, api_token = _credentials(db)
    params = {"jql": "assignee = currentUser() ORDER BY updated DESC", "maxResults": 100, "fields": "summary,status,priority,assignee"}
    try:
        response = httpx.get(f"{base_url}/rest/api/3/search/jql", params=params, headers=_headers(email, api_token), timeout=20)
        if response.status_code in (404, 410):
            response = httpx.get(f"{base_url}/rest/api/3/search", params=params, headers=_headers(email, api_token), timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or assigned issue permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while loading assigned issues.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable.") from exc

    today = datetime.now(timezone.utc).date()
    missing = []
    for item in response.json().get("issues", []):
        issue_key = item.get("key", "")
        try:
            comments_response = httpx.get(f"{base_url}/rest/api/3/issue/{issue_key}/comment", params={"maxResults": 100, "orderBy": "-created"}, headers=_headers(email, api_token), timeout=20)
            comments_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise RuntimeError("Jira rejected the credentials or comment permission.") from exc
            raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while loading comments.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Jira is temporarily unavailable.") from exc
        has_comment_today = any(
            comment.get("created") and datetime.fromisoformat(comment["created"].replace("Z", "+00:00")).date() == today
            for comment in comments_response.json().get("comments", [])
        )
        if not has_comment_today:
            fields = item.get("fields") or {}
            missing.append({"key": issue_key, "summary": fields.get("summary", "Jira issue"), "status": (fields.get("status") or {}).get("name", "Unknown"), "priority": (fields.get("priority") or {}).get("name", "Unassigned"), "assignee": (fields.get("assignee") or {}).get("displayName", email), "url": f"{base_url}/browse/{issue_key}"})
    return missing