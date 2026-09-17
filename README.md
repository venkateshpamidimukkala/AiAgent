# Unified Voice Assistant

An extensible FastAPI + Angular MVP for ranking work communications, drafting replies, and voice interaction.

## Run locally

### Backend

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API uses SQLite by default and seeds demo data. Set `DATABASE_URL` to PostgreSQL for production.

Confluence and Jira connections entered in the UI are saved in the configured database (`integration_credentials`) and reused automatically after backend restarts. For production, use PostgreSQL, protect database access, and encrypt provider tokens at rest.

## Connect Outlook and Teams

Outlook and Teams use Microsoft Graph, so one Microsoft OAuth connection authorizes both services.

1. Open the Microsoft Entra admin center and go to **App registrations → New registration**.
2. Select **Accounts in any organizational directory and personal Microsoft accounts** for local testing.
3. Add this Web redirect URI exactly: `http://localhost:8000/api/auth/microsoft/callback`.
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
3. Add this Web redirect URI exactly: `http://localhost:8000/api/auth/microsoft/callback`.
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

Open `http://localhost:4200`. API requests are proxied to `http://localhost:8000`.

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
