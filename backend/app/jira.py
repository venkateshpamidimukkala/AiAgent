import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlparse

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


def _text_from_adf(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    return "".join(_text_from_adf(child) for child in value.get("content", []))


def _jira_request(method: str, url: str, email: str, api_token: str, **kwargs: Any) -> httpx.Response:
    response = httpx.request(method, url, headers={**_headers(email, api_token), **kwargs.pop("headers", {})}, timeout=20, **kwargs)
    if response.status_code in (401, 403):
        raise RuntimeError("Jira rejected the credentials or permission for this operation.")
    if response.status_code >= 400:
        detail = ""
        try:
            error_body = response.json()
            errors = error_body.get("errors") or {}
            messages = error_body.get("errorMessages") or []
            detail = "; ".join([*messages, *[str(value) for value in errors.values()]])
        except (ValueError, TypeError):
            detail = response.text.strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"Jira returned HTTP {response.status_code}{suffix}")
    return response


def search_issues(query: str, board_name: str = "", db=None) -> list[dict[str, Any]]:
    base_url, email, api_token = _credentials(db)
    query = query.strip()
    board_name = board_name.strip()
    if not query and not board_name:
        raise ValueError("Enter a Jira issue search or question.")
    escaped = query.replace('"', '\\"')
    jql = f'text ~ "{escaped}" ORDER BY updated DESC' if query else ""
    fields = "summary,description,status,priority,assignee,updated"
    try:
        # Jira Cloud deprecated /rest/api/3/search in favour of /search/jql.
        # Keep the old endpoint as a compatibility fallback for older Jira
        # Server/Data Center installations.
        if board_name:
            boards = _jira_request("GET", f"{base_url}/rest/agile/1.0/board", email, api_token, params={"name": board_name, "maxResults": 50})
            board = next((item for item in boards.json().get("values", []) if item.get("name", "").casefold() == board_name.casefold()), None)
            if board is None:
                raise ValueError(f'Jira board "{board_name}" was not found.')
            issues = []
            start_at = 0
            while True:
                params = {"startAt": start_at, "maxResults": 50, "fields": fields}
                if jql:
                    params["jql"] = jql
                response = _jira_request("GET", f"{base_url}/rest/agile/1.0/board/{board['id']}/issue", email, api_token, params=params)
                page = response.json()
                page_issues = page.get("issues", [])
                issues.extend(page_issues)
                if page.get("isLast", False) or not page_issues:
                    break
                start_at += len(page_issues)
        else:
            params = {"jql": jql, "maxResults": 100, "fields": fields}
            response = httpx.get(f"{base_url}/rest/api/3/search/jql", params=params, headers=_headers(email, api_token), timeout=20)
            if response.status_code in (404, 410):
                response = httpx.get(f"{base_url}/rest/api/3/search", params=params, headers=_headers(email, api_token), timeout=20)
            response.raise_for_status()
            issues = response.json().get("issues", [])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or issue search permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while searching.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable.") from exc
    results = []
    for item in issues:
        fields = item.get("fields") or {}
        results.append({
            "key": item.get("key", ""),
            "summary": fields.get("summary", "Jira issue"),
            "status": (fields.get("status") or {}).get("name", "Unknown"),
            "priority": (fields.get("priority") or {}).get("name", "Unassigned"),
            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
            "updated": fields.get("updated"),
            "url": f"{base_url}/browse/{item.get('key', '')}",
        })
    return results


def _assigned_issue_group(status: str) -> str:
    normalized = status.casefold()
    if any(value in normalized for value in ("done", "closed", "resolved", "complete")):
        return "Done"
    if any(value in normalized for value in ("block", "impediment")):
        return "Blocked"
    if any(value in normalized for value in ("review", "test", "qa", "uat")):
        return "Review/Testing"
    if any(value in normalized for value in ("progress", "development", "developing")):
        return "In Progress"
    return "To Do"


def _field_value(fields: dict[str, Any], field_ids: set[str]) -> Any:
    for field_id in field_ids:
        if fields.get(field_id) is not None:
            return fields[field_id]
    return None


def _sprint_name(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[-1] if value else None
    if isinstance(value, dict):
        return value.get("name") or value.get("value")
    if isinstance(value, str):
        # Jira Cloud commonly returns sprint values as serialized objects.
        for part in value.split(","):
            if part.strip().startswith("name="):
                return part.split("=", 1)[1].strip()
        return value
    return None


def _custom_field_ids(field_metadata: list[dict[str, Any]], terms: tuple[str, ...], fallbacks: set[str]) -> set[str]:
    result = set(fallbacks)
    for field in field_metadata:
        name = str(field.get("name", "")).casefold()
        if any(term in name for term in terms):
            field_id = field.get("id")
            if field_id:
                result.add(field_id)
    return result


def assigned_issues_report(db=None) -> dict[str, Any]:
    """Return all issues assigned to the authenticated Jira user and report metrics."""
    base_url, email, api_token = _credentials(db)
    jql = "assignee = currentUser() ORDER BY updated DESC"
    fields = "summary,status,priority,assignee,project,duedate,created,updated,customfield_10016,customfield_10020"
    try:
        metadata_response = _jira_request("GET", f"{base_url}/rest/api/3/field", email, api_token)
        field_metadata = metadata_response.json()
    except (RuntimeError, httpx.HTTPError):
        field_metadata = []
    sprint_ids = _custom_field_ids(field_metadata, ("sprint",), {"customfield_10020"})
    story_point_ids = _custom_field_ids(field_metadata, ("story point", "story points"), {"customfield_10016"})
    fields = ",".join(dict.fromkeys([*fields.split(","), *sprint_ids, *story_point_ids]))

    issues: list[dict[str, Any]] = []
    try:
        next_page_token = None
        while True:
            params = {"jql": jql, "maxResults": 100, "fields": fields}
            if next_page_token:
                params["nextPageToken"] = next_page_token
            response = httpx.get(f"{base_url}/rest/api/3/search/jql", params=params, headers=_headers(email, api_token), timeout=20)
            if response.status_code in (404, 410):
                break
            response.raise_for_status()
            page = response.json()
            page_issues = page.get("issues", [])
            issues.extend(page_issues)
            next_page_token = page.get("nextPageToken")
            if not next_page_token or not page_issues:
                break
        if not issues and response.status_code in (404, 410):
            start_at = 0
            while True:
                response = httpx.get(f"{base_url}/rest/api/3/search", params={"jql": jql, "startAt": start_at, "maxResults": 100, "fields": fields}, headers=_headers(email, api_token), timeout=20)
                response.raise_for_status()
                page = response.json()
                page_issues = page.get("issues", [])
                issues.extend(page_issues)
                if not page_issues or start_at + len(page_issues) >= page.get("total", 0):
                    break
                start_at += len(page_issues)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Jira rejected the credentials or assigned issue permission.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while loading assigned issues.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Jira is temporarily unavailable.") from exc

    today = datetime.now(timezone.utc).date()
    seven_days_ago = today - timedelta(days=7)
    groups = {name: [] for name in ("In Progress", "To Do", "Blocked", "Review/Testing", "Done")}
    normalized_issues = []
    for item in issues:
        values = item.get("fields") or {}
        status = (values.get("status") or {}).get("name", "Unknown")
        priority = (values.get("priority") or {}).get("name", "Unassigned")
        due_date = values.get("duedate")
        updated = values.get("updated")
        issue = {
            "issue_key": item.get("key", ""),
            "summary": values.get("summary", "Jira issue"),
            "status": status,
            "priority": priority,
            "sprint": _sprint_name(_field_value(values, sprint_ids)),
            "project": (values.get("project") or {}).get("name") or (values.get("project") or {}).get("key"),
            "assignee": (values.get("assignee") or {}).get("displayName", email),
            "story_points": _field_value(values, story_point_ids),
            "due_date": due_date,
            "created_date": values.get("created"),
            "updated_date": updated,
            "issue_url": f"{base_url}/browse/{item.get('key', '')}",
        }
        normalized_issues.append(issue)
        groups[_assigned_issue_group(status)].append(issue)

    def issue_date(issue: dict[str, Any], key: str):
        value = issue.get(key)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date() if value else None

    high_priority = [issue for issue in normalized_issues if issue["priority"].casefold() in {"highest", "high", "critical", "blocker"}]
    overdue = [issue for issue in normalized_issues if issue["due_date"] and issue_date(issue, "due_date") < today and issue["status"].casefold() != "done"]
    recently_updated = [issue for issue in normalized_issues if issue_date(issue, "updated_date") and issue_date(issue, "updated_date") >= seven_days_ago]
    return {
        "jql": jql,
        "total_ticket_count": len(normalized_issues),
        "count_per_status": {status: sum(issue["status"] == status for issue in normalized_issues) for status in sorted({issue["status"] for issue in normalized_issues})},
        "high_priority_tickets": high_priority,
        "overdue_tickets": overdue,
        "updated_last_7_days": recently_updated,
        "groups": groups,
    }


def get_issue(issue_key: str, db=None) -> dict[str, Any]:
    """Load one Jira issue by its exact key, including fields used by the UI."""
    base_url, email, api_token = _credentials(db)
    issue_key = issue_key.strip()
    if not issue_key:
        raise ValueError("Enter a Jira issue key.")
    fields = "summary,description,status,priority,assignee,updated,duedate,issuetype,labels"
    try:
        response = _jira_request(
            "GET",
            f"{base_url}/rest/api/3/issue/{quote(issue_key, safe='')}",
            email,
            api_token,
            params={"fields": fields},
        )
    except RuntimeError as exc:
        raise RuntimeError(f"Unable to load Jira issue {issue_key}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while loading issue {issue_key}.") from exc

    item = response.json()
    values = item.get("fields") or {}
    return {
        "key": item.get("key", issue_key),
        "summary": values.get("summary", "Jira issue"),
        "status": (values.get("status") or {}).get("name", "Unknown"),
        "priority": (values.get("priority") or {}).get("name", "Unassigned"),
        "assignee": (values.get("assignee") or {}).get("displayName", "Unassigned"),
        "updated": values.get("updated"),
        "url": f"{base_url}/browse/{item.get('key', issue_key)}",
        "description": _text_from_adf(values.get("description")),
        "issue_type": (values.get("issuetype") or {}).get("name", "Task"),
        "labels": values.get("labels") or [],
        "due_date": values.get("duedate"),
    }


def issue_comments(issue_key: str, db=None) -> list[dict[str, Any]]:
    base_url, email, api_token = _credentials(db)
    try:
        response = _jira_request("GET", f"{base_url}/rest/api/3/issue/{quote(issue_key.strip(), safe='')}/comment", email, api_token, params={"maxResults": 100, "orderBy": "created"})
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Jira returned HTTP {exc.response.status_code} while loading comments.") from exc
    return [{
        "id": comment.get("id", ""),
        "author": (comment.get("author") or {}).get("displayName", "Jira user"),
        "created": comment.get("created"),
        "body": _text_from_adf(comment.get("body")),
    } for comment in response.json().get("comments", [])]


def add_comment(issue_key: str, body: str, reply_to: str | None = None, db=None) -> None:
    base_url, email, api_token = _credentials(db)
    issue_key = issue_key.strip()
    body = body.strip()
    if not issue_key or not body:
        raise ValueError("Enter a Jira issue key and comment.")
    if reply_to:
        body = f"Reply to Jira comment {reply_to}:\n\n{body.strip()}"
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}}
    try:
        _jira_request("POST", f"{base_url}/rest/api/3/issue/{quote(issue_key, safe='')}/comment", email, api_token, json=payload, headers={"Content-Type": "application/json"})
    except RuntimeError as exc:
        if str(exc) == "Jira rejected the credentials or permission for this operation.":
            raise RuntimeError("Jira rejected the credentials or comment permission.") from exc
        raise RuntimeError(f"Unable to add the Jira comment: {exc}") from exc
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