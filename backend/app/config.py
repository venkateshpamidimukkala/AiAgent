from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:admin@127.0.0.1:5432/postgres"
    frontend_origin: str = "http://localhost:4300"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_stt_model: str = "whisper-1"
    google_translate_api_key: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = "http://localhost:8100/api/auth/microsoft/callback"
    microsoft_scopes: str = "User.Read offline_access Mail.ReadWrite Mail.Send Calendars.Read Chat.Read ChannelMessage.Read.All Team.ReadBasic.All"
    confluence_base_url: str | None = None
    confluence_email: str | None = None
    confluence_api_token: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    # Resolve this relative to the backend package so starting uvicorn from the
    # repository root or another working directory still loads backend/.env.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
