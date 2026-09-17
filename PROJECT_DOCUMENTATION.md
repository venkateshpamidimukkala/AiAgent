# Unified Voice Assistant

## 1. Project Overview

Unified Voice Assistant is a full-stack workplace productivity assistant that brings work communications and company knowledge into one interface. The application provides a prioritized inbox, assistant-generated replies, voice interaction, Microsoft Outlook and Teams synchronization, and Confluence-grounded question answering.

The project is implemented as an Angular frontend and a FastAPI backend. It supports local development with SQLite and production-style deployment with PostgreSQL and Docker Compose.

### Primary goals

- Reduce time spent reviewing work messages.
- Rank incoming work items by urgency and business priority.
- Generate and revise draft replies before sending.
- Provide voice input and optional text-to-speech output.
- Synchronize Outlook and Teams messages through Microsoft Graph.
- Answer natural-language questions using content from Confluence.
- Keep provider credentials outside the source code.

## 2. Main Features

### 2.1 Priority inbox

The dashboard displays messages ordered by AI-style priority score. Each message contains:

- Source provider
- Sender
- Subject
- Body preview
- Priority score
- Priority label
- Creation or received time

The backend stores messages in the `messages` table and calculates the initial priority using the priority scoring module.

### 2.2 Assistant queries

Users can ask the workspace assistant questions such as:

- `Show me my highest impact decisions`
- `Summarize today's important work`
- `Which messages need a response?`

The backend matches query terms against stored workspace messages and sends the matching context to the answer function. Requests and responses are stored in the `assistant_requests` table for history and auditing.

### 2.3 Draft reply generation

A user can select a message and create a reply draft. The draft can be revised with instructions such as:

- `Make it formal`
- `Shorten this`
- `Mention the delivery date`

The user must explicitly send the draft. The current provider dispatch layer returns a demo provider ID and is intended to be replaced by production email or messaging clients.

### 2.4 Voice assistant

The browser voice interface supports:

- Speech recognition through browser `SpeechRecognition` or `webkitSpeechRecognition`.
- Multiple voice styles.
- Configurable input and output language.
- Browser speech synthesis.
- Optional OpenAI-backed audio transcription.
- Optional translation before speech output.

Browser support for speech recognition and speech synthesis varies by browser and operating system.

### 2.5 Microsoft Outlook and Teams integration

Outlook and Teams use one Microsoft Entra ID OAuth flow. After authentication, the backend stores the Microsoft token in the `oauth_tokens` table and synchronizes:

- Outlook inbox messages
- Microsoft Teams chats
- Joined Teams and channel messages

The integration requires Microsoft Graph delegated permissions. See the configuration section for the required permissions.

### 2.6 Confluence integration

The Confluence integration supports both page-specific questions and workspace-level natural-language prompts.

When a user connects Confluence through the UI, the normalized site URL, account email, and API token are saved in the PostgreSQL `integration_credentials` table. Subsequent status, page, and question requests load the saved credentials automatically, including after a backend restart. Disconnecting removes the saved provider credentials. API responses never return the stored token.

### 2.7 Jira integration

Jira uses the same persistent connection flow as Confluence. Enter the Atlassian site URL, account email, and API token once. A successful connection is saved in PostgreSQL and is automatically reused for Jira status and issue searches. The Jira client validates credentials through `/rest/api/3/myself` before saving them.

Example site URL:

```text
https://pncilab-team.atlassian.net
```

An administration URL can also be entered during connection:

```text
https://pncilab-team.atlassian.net/wiki/admin/configuration
```

The backend normalizes it to the site root before making API requests.

Supported use cases:

- Ask a prompt across the connected Confluence workspace.
- Search matching pages using Confluence CQL.
- Retrieve page content and metadata.
- Ask questions about a specific Confluence page URL.
- Display the generated answer and source page link in the frontend.

Example prompts:

```text
What is our deployment process?
```

```text
Summarize the onboarding documentation.
```

```text
What are the current production risks?
```

```text
Find the API configuration guidelines.
```

The Confluence API token must have permission to search and read the required spaces and pages.

## 3. Technology Stack

### Frontend

- Angular 19
- TypeScript 5.6
- RxJS 7.8
- Angular Forms
- Angular HttpClient
- Browser Speech Recognition API
- Browser Speech Synthesis API
- Nginx for container serving

### Backend

- Python 3.12 container target
- FastAPI 0.115
- Uvicorn
- SQLAlchemy 2
- Pydantic Settings
- HTTPX
- Microsoft Authentication Library for Python
- OpenAI SDK
- PostgreSQL driver through `psycopg`
- SQLite for local default operation

### Infrastructure

- Docker Compose
- PostgreSQL 16 with pgvector image
- Nginx
- Angular development proxy

## 4. Repository Structure

```text
AiAgent/
├── .env.example
├── backend/
│   ├── app/
│   │   ├── ai.py
│   │   ├── config.py
│   │   ├── confluence.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── microsoft_auth.py
│   │   ├── microsoft_graph.py
│   │   ├── models.py
│   │   ├── priority.py
│   │   ├── providers.py
│   │   └── schemas.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app.component.ts
│   │   ├── app.component.html
│   │   └── styles.css
│   ├── Dockerfile
│   ├── angular.json
│   ├── package.json
│   └── proxy.conf.json
├── docker-compose.yml
├── start-app.bat
├── README.md
└── PROJECT_DOCUMENTATION.md
```

## 5. Local Development Setup

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- PostgreSQL only if using a PostgreSQL database locally
- Docker Desktop if using Docker Compose

### Option A: Start with the Windows launcher

Run the following file from the project root:

```text
start-app.bat
```

The launcher creates the backend virtual environment if required, installs backend dependencies, installs frontend dependencies if required, and starts:

- Backend: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`
- Frontend: `http://localhost:4200`

### Option B: Start the backend manually

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start the frontend manually

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\frontend
npm install
npm start
```

Open:

```text
http://localhost:4200
```

The Angular development proxy forwards `/api` requests to:

```text
http://localhost:8000
```

### Option C: Docker Compose

```powershell
docker compose up --build
```

Docker Compose starts:

- PostgreSQL on port `5432`
- FastAPI on port `8000`
- Angular/Nginx on port `4200`

## 6. Environment Configuration

Copy `.env.example` to `backend/.env` and set values appropriate for the environment.

```dotenv
DATABASE_URL=postgresql+psycopg://assistant:admin@localhost:5432/assistant
FRONTEND_ORIGIN=http://localhost:4200

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_STT_MODEL=whisper-1

MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=common
MICROSOFT_REDIRECT_URI=http://localhost:8000/api/auth/microsoft/callback
MICROSOFT_SCOPES=User.Read offline_access Mail.ReadWrite Mail.Send Chat.Read ChannelMessage.Read.All Team.ReadBasic.All

CONFLUENCE_BASE_URL=https://your-company.atlassian.net
CONFLUENCE_EMAIL=
CONFLUENCE_API_TOKEN=
```

Never commit the following values:

- OpenAI API keys
- Microsoft client secrets
- Microsoft OAuth access or refresh tokens
- Confluence API tokens
- Production database passwords

## 7. Microsoft OAuth Configuration

1. Open Microsoft Entra admin center.
2. Go to **App registrations**.
3. Create a new application registration.
4. Add this redirect URI:

```text
http://localhost:8000/api/auth/microsoft/callback
```

5. Copy the application client ID.
6. Create a client secret and copy its value immediately.
7. Add delegated Microsoft Graph permissions:

- `User.Read`
- `offline_access`
- `Mail.ReadWrite`
- `Mail.Send`
- `Chat.Read`
- `ChannelMessage.Read.All`
- `Team.ReadBasic.All`

8. Put the client ID and secret in `backend/.env`.
9. Restart the backend.
10. Use **Connect Outlook + Teams** in the application.

## 8. Confluence Configuration

### Create an Atlassian API token

1. Sign in to the Atlassian account that can read the required Confluence spaces.
2. Create an API token from the Atlassian account security settings.
3. Keep the token private.

### Connect from the UI

Enter:

- Site URL: `https://your-company.atlassian.net`
- Atlassian account email
- Atlassian API token

The backend strips paths such as `/wiki/admin/configuration` and stores only the Atlassian site origin.

### Confluence request flow

1. Frontend sends credentials to `POST /api/confluence/connect`.
2. Backend stores credentials in runtime memory or loads them from environment settings.
3. Frontend sends a prompt to `POST /api/confluence/ask`.
4. Backend searches Confluence using the content search endpoint and CQL.
5. Matching page content is cleaned from HTML storage format.
6. The answer service generates a grounded answer.
7. The response includes the answer and a source page URL.
8. Frontend displays both in the Confluence response panel.

### Confluence permissions

The API token user must be able to:

- Log in to the Atlassian site.
- Search Confluence content.
- Read the target spaces and pages.
- Access the content through the Confluence Cloud REST API.

## 9. API Reference

### Health

#### `GET /api/health`

Returns service and database status.

Example response:

```json
{
  "status": "ok",
  "database": "non-postgresql"
}
```

### Workspace assistant

#### `POST /api/assistant/query`

Request:

```json
{
  "query": "Show my highest impact decisions",
  "request_type": "workspace"
}
```

#### `GET /api/assistant/requests?limit=20`

Returns recent assistant requests and completed responses.

### Messages

#### `GET /api/messages?limit=20`

Returns priority-ranked messages.

#### `GET /api/messages/{message_id}`

Returns one message by ID.

#### `POST /api/messages/sync`

Synchronizes Outlook and Teams messages through Microsoft Graph.

### Draft replies

#### `POST /api/replies/draft`

Request:

```json
{
  "message_id": 1,
  "instruction": "Reply that I will review this today"
}
```

#### `POST /api/replies/{draft_id}/revise`

Request:

```json
{
  "instruction": "Make it more formal"
}
```

#### `POST /api/replies/{draft_id}/send`

Sends or dispatches a confirmed draft. The current implementation uses a demo provider boundary.

### Microsoft authentication

- `GET /api/auth/microsoft/status`
- `GET /api/auth/microsoft/login`
- `GET /api/auth/microsoft/callback`
- `POST /api/auth/microsoft/disconnect`

### Confluence

#### `GET /api/confluence/status`

Returns whether Confluence credentials are configured and the normalized site URL.

#### `POST /api/confluence/connect`

Request:

```json
{
  "base_url": "https://your-company.atlassian.net/wiki/admin/configuration",
  "email": "user@example.com",
  "api_token": "REPLACE_WITH_TOKEN"
}
```

The response hides the token.

#### `POST /api/confluence/page`

Fetches a specific page. The URL must contain `/pages/{page-id}`, `pageId={page-id}`, or be a numeric page ID.

Request:

```json
{
  "url": "https://your-company.atlassian.net/wiki/spaces/ENG/pages/123456789/Page+Title"
}
```

#### `POST /api/confluence/ask`

Workspace prompt request:

```json
{
  "url": "",
  "question": "What is our deployment process?"
}
```

Page-grounded request:

```json
{
  "url": "https://your-company.atlassian.net/wiki/spaces/ENG/pages/123456789/Page+Title",
  "question": "Summarize this page"
}
```

Example response:

```json
{
  "answer": "The deployment process is ...",
  "source": {
    "title": "Deployment Process",
    "url": "https://your-company.atlassian.net/wiki/spaces/ENG/pages/123456789/Page+Title"
  }
}
```

### Voice

- `POST /api/voice/transcribe` accepts an audio upload.
- `POST /api/voice/translate` translates text for voice output when OpenAI is configured.

## 10. Data Model

### `messages`

Stores inbox and synchronized communication items.

Important fields:

- `source`
- `external_id`
- `sender`
- `subject`
- `body`
- `thread_id`
- `priority_score`
- `priority_label`
- `created_at`

### `draft_replies`

Stores generated replies and their lifecycle status.

Important fields:

- `message_id`
- `draft_text`
- `status`
- `created_at`

### `oauth_tokens`

Stores Microsoft OAuth credentials and account metadata.

Important fields:

- `provider`
- `access_token`
- `refresh_token`
- `expires_at`
- `account_email`

### `assistant_requests`

Stores assistant prompts, generated responses, status, errors, and timestamps.

## 11. AI and Fallback Behavior

When `OPENAI_API_KEY` is configured:

- Draft replies use the configured OpenAI model.
- Confluence answers use the configured OpenAI model.
- Voice transcription uses the configured speech-to-text model.
- Voice translation uses the configured OpenAI model.

When OpenAI is not configured:

- The application remains usable with deterministic local fallback responses.
- Draft replies use a safe template.
- Confluence summaries and term matching use local text processing.
- Voice transcription returns a configuration message rather than making an external request.

## 12. Error Handling

Common errors include:

### Confluence is not configured

Cause: site URL, email, or API token is missing.

Resolution: configure all three values and reconnect.

### Confluence rejected credentials or permissions

Cause: invalid API token, wrong email, expired token, or insufficient page permissions.

Resolution: create a new Atlassian API token and confirm the user can open the requested Confluence page.

### No Confluence response

Cause: the input is an admin URL used as if it were a page URL, the search has no matching pages, or the frontend is still using stale backend code.

Resolution:

1. Restart the backend.
2. Disconnect and reconnect Confluence.
3. Use a natural-language question in the prompt field.
4. Confirm the API token can read Confluence content.
5. Review the browser Network tab and backend console output.

### Microsoft Graph synchronization failure

Cause: missing delegated permissions, expired OAuth token, or administrator consent not granted.

Resolution: reconnect Microsoft and verify Graph permissions.

## 13. Security and Production Recommendations

- Use HTTPS for frontend and backend traffic.
- Store secrets in a secret manager instead of plain `.env` files.
- Encrypt OAuth tokens at rest.
- Do not log API tokens or access tokens.
- Use least-privilege Microsoft Graph permissions.
- Restrict Confluence access to approved spaces where possible.
- Add authentication and authorization for the FastAPI endpoints.
- Replace runtime-only Confluence credential storage with encrypted persistent storage for multi-user deployments.
- Use database migrations instead of `Base.metadata.create_all` for production schema changes.
- Configure structured logging and monitoring.
- Add rate limits for external API calls.
- Validate and restrict allowed frontend origins.
- Replace the demo dispatch provider before enabling production message sending.

## 14. Testing and Validation

### Frontend build

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\frontend
npm run build
```

### Backend compilation

```powershell
cd C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent\backend
.\.venv\Scripts\python.exe -m compileall -q app
```

### API documentation

With the backend running, open:

```text
http://localhost:8000/docs
```

### Manual Confluence test

1. Start backend and frontend.
2. Open `http://localhost:4200`.
3. Select **Confluence**.
4. Enter the Atlassian site URL, email, and API token.
5. Confirm the status changes to **Connected**.
6. Enter: `What is our deployment process?`
7. Confirm an answer appears in the response panel.
8. Confirm a source page link appears.
9. Test a page-specific URL containing a page ID.
10. Test invalid credentials and verify a visible error message.

## 15. Current Implementation Limitations

- The message send provider is currently a demo implementation.
- Confluence and Jira credentials entered through the UI are persisted in PostgreSQL and automatically reused after backend restarts. The current single-user MVP stores tokens as database values; production deployments should encrypt them at rest and add user/tenant ownership.
- The local SQLite database is suitable for development and demonstration, not production scale.
- OpenAI functionality is optional and requires an API key.
- Browser speech recognition is not available in every browser.
- No automated test suite is currently included in the repository.
- Production authentication and per-user authorization still need to be added.
- Docker Nginx serving is configured for the container build, while local Angular development uses `ng serve`.

## 16. Recommended Future Enhancements

- Add automated unit, integration, and end-to-end tests.
- Add Confluence space filters and page-result selection.
- Encrypt persistent provider credentials and associate them with authenticated users or tenants.
- Add answer citations for every paragraph or claim.
- Add pagination and incremental synchronization.
- Add background jobs for Microsoft and Confluence synchronization.
- Add provider health dashboards.
- Add user accounts and tenant isolation.
- Add database migrations with Alembic.
- Replace demo outbound providers with real provider adapters.

## 17. Ownership and Support Information

### Local service URLs

| Service | URL |
|---|---|
| Frontend | `http://localhost:4200` |
| Backend | `http://localhost:8000` |
| API documentation | `http://localhost:8000/docs` |
| Health check | `http://localhost:8000/api/health` |
| PostgreSQL | `localhost:5432` |

### Project location

```text
C:\Users\GCCHackVM\hackthon\PNCAgent\AiAgent
```

### Startup command

```text
start-app.bat
```

