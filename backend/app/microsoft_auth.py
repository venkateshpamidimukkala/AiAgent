from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any
import msal
from fastapi import HTTPException
from .config import settings

_pending_states: set[str] = set()


def configured() -> bool:
    return bool(settings.microsoft_client_id and settings.microsoft_client_secret)


def _client() -> msal.ConfidentialClientApplication:
    if not configured():
        raise HTTPException(503, "Microsoft OAuth is not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in backend/.env.")
    return msal.ConfidentialClientApplication(
        settings.microsoft_client_id,
        authority=f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}",
        client_credential=settings.microsoft_client_secret,
    )


def scopes() -> list[str]:
    return settings.microsoft_scopes.split()


def authorization_url() -> str:
    state = token_urlsafe(32)
    _pending_states.add(state)
    return _client().get_authorization_request_url(scopes(), state=state, redirect_uri=settings.microsoft_redirect_uri, prompt="select_account")


def exchange_code(code: str, state: str) -> dict[str, Any]:
    if state not in _pending_states:
        raise HTTPException(400, "Invalid or expired Microsoft OAuth state.")
    _pending_states.remove(state)
    result = _client().acquire_token_by_authorization_code(code, scopes=scopes(), redirect_uri=settings.microsoft_redirect_uri)
    if "access_token" not in result:
        raise HTTPException(400, result.get("error_description", "Microsoft authorization failed."))
    return result


def token_expiry(result: dict[str, Any]) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=int(result.get("expires_in", 3600)))
