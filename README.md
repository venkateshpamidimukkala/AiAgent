# Unified Voice Assistant

An extensible FastAPI + Angular MVP for ranking work communications, drafting replies, and voice interaction.

## Run locally

### Backend

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\backend
python -m venv .venv  # only needed once
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
\.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Alternatively, from this `backend` directory, run `run-backend.bat`. It always
uses the project's virtual-environment interpreter and validates `msal` before
starting Uvicorn. If you prefer activation, use:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Do not start this backend with a different global interpreter such as
`C:\Python314\python.exe`; it does not contain the project's dependencies (for
example, `msal`). A command prompt showing only `backend>` does not prove that
the virtual environment is active; the explicit `.venv\Scripts\python.exe`
command or `run-backend.bat` avoids that ambiguity.

When `--reload` detects a source-file change, Uvicorn intentionally stops the
old worker and starts a new one. The `Shutting down` messages are expected; a
`CancelledError` from Starlette's lifespan wait can also be printed by older
Uvicorn versions during that normal restart. This project pins a current
Uvicorn release for Python 3.14-compatible reload/shutdown handling. If a
Windows reinstall leaves temporary `~vicorn` folders in `.venv`, remove those
folders and reinstall the requirements before starting the server. A
successful request such as `200 OK` is not affected by that restart message.

The API uses SQLite by default and seeds demo data. Set `DATABASE_URL` to PostgreSQL for production.

Confluence and Jira connections entered in the UI are saved in the configured database (`integration_credentials`) and reused automatically after backend restarts. For production, use PostgreSQL, protect database access, and encrypt provider tokens at rest.

## Connect Outlook and Teams

Outlook and Teams use Microsoft Graph, so one Microsoft OAuth connection authorizes both services.

1. Open the Microsoft Entra admin center and go to **App registrations → New registration**.
2. Select **Accounts in any organizational directory and personal Microsoft accounts** for local testing.
3. Add this Web redirect URI exactly: `http://localhost:8100/api/auth/microsoft/callback`.
4. Copy the **Application (client) ID**.
5. Go to **Certificates & secrets → New client secret** and copy the secret value immediately.
6. Under **API permissions → Microsoft Graph → Delegated permissions**, add `User.Read`, `offline_access`, `Mail.ReadWrite`, `Mail.Send`, `Chat.Read`, `ChannelMessage.Read.All`, and `Team.ReadBasic.All`.
7. Copy `.env.example` to `backend/.env` and fill in `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`.
8. Restart `start-app.bat`, open the dashboard, and click **Connect Outlook + Teams**.

The browser will open Microsoft sign-in. After consent, it returns to the dashboard. Never commit `backend/.env` or the client secret.

## Connect Outlook and Teams

Outlook and Teams use Microsoft Graph, so one Microsoft OAuth connection authorizes both services.

1. Open [Microsoft Entra admin center](https://entra.microsoft.com/) and go to **App registrations → New registration**.
2. Select **Accounts in any organizational directory and personal Microsoft accounts** for local testing.
3. Add this Web redirect URI exactly: `http://localhost:8100/api/auth/microsoft/callback`.
4. Copy the **Application (client) ID**.
5. Go to **Certificates & secrets → New client secret** and copy the secret value immediately.
6. Under **API permissions → Microsoft Graph → Delegated permissions**, add:
   - `User.Read`
   - `offline_access`
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `Chat.Read`
   - `ChannelMessage.Read.All`
   - `Team.ReadBasic.All`
7. Copy `.env.example` to `backend/.env` and fill in `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`.
8. Restart `start-app.bat`, open the dashboard, and click **Connect Outlook + Teams**.

The browser will open Microsoft sign-in. After consent, it returns to the dashboard. Never commit `backend/.env` or the client secret.

### Frontend

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\frontend
npm install
npm start
```

Open `http://localhost:4300`. API requests are proxied to `http://localhost:8100`.

### Docker

```powershell
docker compose up --build
```

## Production integration notes

Provider credentials are deliberately not hard-coded. Configure OAuth applications, encrypt tokens at rest, and replace the demo provider adapters in `backend/app/providers.py` with Gmail, Microsoft Graph, Teams, Jira, and Confluence clients. `OPENAI_API_KEY` enables optional Whisper and LLM drafting; without it, safe local fallbacks keep the demo usable.

## API

- `GET /api/messages?limit=20` ranked priority items
- `GET /api/messages/{id}` item details
- `POST /api/replies/draft` create a draft
- `POST /api/replies/{id}/revise` revise (`formal`, `shorten`, or free-form instruction)
- `POST /api/replies/{id}/send` dispatch after confirmation
- `POST /api/voice/transcribe` Whisper-compatible audio upload
- `POST /api/voice/synthesize` returns speech audio when configured
- `GET /api/health`
- `GET /api/auth/microsoft/status`
- `GET /api/auth/microsoft/login`
- `GET /api/auth/microsoft/callback`
- `POST /api/auth/microsoft/disconnect`
- `GET /api/auth/microsoft/status`
- `GET /api/auth/microsoft/login`
- `GET /api/auth/microsoft/callback`
- `POST /api/auth/microsoft/disconnect`
