import base64
import re
from html import unescape
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from .config import settings
from .models import IntegrationCredential


_runtime_credentials: dict[str, str] = {}


def restore(db=None) -> bool:
    """Load saved Confluence credentials into the process after a backend restart."""
    saved = db.query(IntegrationCredential).filter_by(provider="confluence").first() if db is not None else None
    if saved is None:
        return False
    _runtime_credentials.update({
        "base_url": saved.base_url,
        "email": saved.email,
        "api_token": saved.api_token,
    })
    return True


def configure(base_url: str, email: str, api_token: str, db=None) -> None:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid Confluence site URL, such as https://company.atlassian.net")
    # Users often paste /wiki/admin/configuration. REST calls must use the site root.
    site_url = f"{parsed.scheme}://{parsed.netloc}"
    values = {"base_url": site_url, "email": email.strip(), "api_token": api_token.strip()}
    _runtime_credentials.update(values)
    if db is not None:
        saved = db.query(IntegrationCredential).filter_by(provider="confluence").first()
        if saved is None:
            saved = IntegrationCredential(provider="confluence", **values)
            db.add(saved)
        else:
            saved.base_url, saved.email, saved.api_token = values.values()
        db.commit()


def disconnect(db=None) -> None:
    _runtime_credentials.clear()
    if db is not None:
        saved = db.query(IntegrationCredential).filter_by(provider="confluence").first()
        if saved is not None:
            db.delete(saved)
            db.commit()


def status(db=None) -> dict[str, Any]:
    saved = db.query(IntegrationCredential).filter_by(provider="confluence").first() if db is not None else None
    configured = bool(_runtime_credentials or saved or (settings.confluence_base_url and settings.confluence_email and settings.confluence_api_token))
    if saved and not _runtime_credentials:
        _runtime_credentials.update({"base_url": saved.base_url, "email": saved.email, "api_token": saved.api_token})
    values = _runtime_credentials or {
        "base_url": settings.confluence_base_url or "",
        "email": settings.confluence_email or "",
        "api_token": settings.confluence_api_token or "",
    }
    return {"configured": configured, "connected": configured, "base_url": values["base_url"], "email": values["email"]}


def _credentials(db=None) -> tuple[str, str, str]:
    saved = db.query(IntegrationCredential).filter_by(provider="confluence").first() if db is not None else None
    values = _runtime_credentials or ({"base_url": saved.base_url, "email": saved.email, "api_token": saved.api_token} if saved else {
        "base_url": settings.confluence_base_url or "",
        "email": settings.confluence_email or "",
        "api_token": settings.confluence_api_token or "",
    })
    if not all(values.values()):
        raise RuntimeError("Confluence is not configured. Add the site URL, email, and API token.")
    return values["base_url"], values["email"], values["api_token"]


def _page_id(url: str) -> str:
    match = re.search(r"/pages/(\d+)", urlparse(url).path)
    if match:
        return match.group(1)
    match = re.search(r"pageId=(\d+)", url)
    if match:
        return match.group(1)
    if url.strip().isdigit():
        return url.strip()
    raise ValueError("Paste a Confluence page link containing /pages/{page-id}.")


def _clean_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(p|li|h[1-6]|tr)>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value).replace("\xa0", " ")
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", value)).strip()


def fetch_page(url: str, db=None) -> dict[str, Any]:
    base_url, email, api_token = _credentials(db)
    page_id = _page_id(url)
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    api_url = f"{base_url}/wiki/rest/api/content/{page_id}"
    try:
        response = httpx.get(api_url, params={"expand": "body.storage,space,version"}, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"}, timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Confluence rejected the credentials or page permission.") from exc
        if exc.response.status_code == 404:
            raise RuntimeError("Confluence page was not found or is not visible to this account.") from exc
        raise RuntimeError(f"Confluence returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Confluence is temporarily unavailable.") from exc
    data = response.json()
    page_url = f"{base_url}/wiki{data.get('_links', {}).get('webui', '')}" if data.get('_links', {}).get('webui') else url
    return {
        "id": data.get("id", page_id),
        "title": data.get("title", "Confluence page"),
        "space": (data.get("space") or {}).get("name", "Confluence"),
        "updated": (data.get("version") or {}).get("when"),
        "url": page_url,
        "content": _clean_html((data.get("body") or {}).get("storage", {}).get("value", "")),
    }


def search_pages(query: str, db=None) -> list[dict[str, Any]]:
    """Search readable Confluence pages for a natural-language prompt."""
    base_url, email, api_token = _credentials(db)
    query = query.strip()
    if not query:
        raise ValueError("Enter a question or a Confluence page URL.")
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    words = re.findall(r"[\w-]{3,}", query)
    cql = "text ~ \"" + " ".join(words[:12]).replace('"', '\\"') + "\""
    api_url = f"{base_url}/wiki/rest/api/content/search"
    try:
        response = httpx.get(api_url, params={"cql": cql, "limit": 5, "expand": "body.storage,space,version"}, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"}, timeout=20)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise RuntimeError("Confluence rejected the credentials or search permission.") from exc
        raise RuntimeError(f"Confluence returned HTTP {exc.response.status_code} while searching.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Confluence is temporarily unavailable.") from exc
    pages = []
    for item in response.json().get("results", []):
        webui = (item.get("_links") or {}).get("webui", "")
        pages.append({
            "id": item.get("id", ""),
            "title": item.get("title", "Confluence page"),
            "space": (item.get("space") or {}).get("name", "Confluence"),
            "updated": (item.get("version") or {}).get("when"),
            "url": f"{base_url}/wiki{webui}" if webui else base_url,
            "content": _clean_html((item.get("body") or {}).get("storage", {}).get("value", "")),
        })
    return pages
