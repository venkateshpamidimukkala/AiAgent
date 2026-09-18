from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any
import msal
from fastapi import HTTPException
from .config import settings

_pending_flows: dict[str, dict[str, Any]] = {}


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
    # MSAL adds the protocol scopes itself. Passing these explicitly causes
    # get_authorization_request_url() to raise ValueError, which otherwise
    # surfaces as a generic 500 from the login endpoint.
    reserved_scopes = {"offline_access", "openid", "profile"}
    return [scope for scope in settings.microsoft_scopes.split() if scope.lower() not in reserved_scopes]


def authorization_url() -> str:
    state = token_urlsafe(32)
    # MSAL's auth-code-flow API generates and retains the PKCE verifier and
    # sends the corresponding S256 challenge in the authorization URL.
    flow = _client().initiate_auth_code_flow(
        scopes(),
        state=state,
        redirect_uri=settings.microsoft_redirect_uri,
        prompt="select_account",
    )
    _pending_flows[state] = flow
    return flow["auth_uri"]


def exchange_code(code: str, state: str) -> dict[str, Any]:
    flow = _pending_flows.pop(state, None)
    if flow is None:
        raise HTTPException(400, "Invalid or expired Microsoft OAuth state.")
    result = _client().acquire_token_by_auth_code_flow(flow, {"code": code, "state": state}, scopes=scopes())
    if "access_token" not in result:
        raise HTTPException(400, result.get("error_description", "Microsoft authorization failed."))
    return result


def token_expiry(result: dict[str, Any]) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=int(result.get("expires_in", 3600)))
