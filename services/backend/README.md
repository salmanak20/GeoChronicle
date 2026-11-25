# GeoChronicle Backend (Phase 4)

Python 3.12 FastAPI service launched and supervised by the Tauri Rust process in development. It provides authenticated project management and research/content intelligence backed by SQLite, in addition to health/readiness and migration workflows. Image/audio generation and video rendering are not included.

## Setup and commands

```powershell
Set-Location 'S:\Projects\GeoChronicle\services\backend'
py -3.12 -m venv .venv  # only if the repository venv does not exist
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe run.py
```

Start the Tauri desktop shell from `apps/desktop` with `npm run tauri dev`. Rust launches the exact interpreter under this `.venv`, generates a fresh per-launch token, selects an OS-assigned port, and waits for authenticated readiness. Binding is loopback-only. Windows socket activation is not used: because the selected port is released before Uvicorn binds, a collision can occur. Rust detects when its launched child exits before readiness and retries up to four times; every request must authenticate with the random token, so the app will not attach to an unrelated listener. Retry exhaustion reports an error in Settings.

The token is passed in `GEOCHRONICLE_AUTH_TOKEN` to the backend process and held by Rust. It is required by `/api/v1/health`, `/api/v1/health/ready`, all `/api/v1/projects` and `/api/v1/content` endpoints, and `POST /api/v1/internal/shutdown`; the shutdown endpoint rejects requests if no token is configured. React receives project/content data, status, and safe error text through Tauri IPC only.

Tauri exit requests authenticated shutdown and waits up to five seconds for the owned Python child. Rust then kills and reaps only that exact child if needed. Startup is bounded to 20 seconds per attempt. The Settings page exposes status refresh and retry; the retry IPC command is available only for the manager's stopped/error lifecycle.

## Database

The default database path is `%LOCALAPPDATA%\GeoChronicle\geochronicle.db`. Override it with `GEOCHRONICLE_DATABASE_URL` for local development. Startup applies Alembic migrations. Migration scripts are under `app/db/migrations`; do not change a persisted schema outside migrations. Tests use per-test temporary SQLite databases.

The desktop redirects backend stdout/stderr to `%LOCALAPPDATA%\GeoChronicle\logs\backend.log` to retain startup diagnostics. The per-launch token is not written to logs.

### Project schema

`Project` retains its Phase 2 integer primary key. It stores name (required, max 200), optional topic (max 500) and description (max 5,000), status (`draft`, `in_progress`, `completed`, `archived`), optional target duration (30–7,200 seconds), aspect ratio (`16:9`, `9:16`, `1:1`, `4:3`), language tag, visual style (`hybrid`, `cinematic`, `animated_maps`), and UTC creation/update timestamps. A topic index and database status constraint support listing and integrity. Alembic revision `0002_project_management` adds the new fields with backward-compatible defaults; it does not remove existing rows.

### Research and content intelligence

Migration `0003_content_intelligence` adds research sessions, deduplicated source records and provenance, claims and source relationships, fact-check suggestions, script documents/sections/versions, storyboard scenes, and narration segments. Existing project rows remain intact. On startup, sessions left `running` by a prior process are marked failed for recovery.

Content routes below `/api/v1/content` require the same bearer authentication as project routes. They support provider status/configuration, research sessions and source details, claim review and fact-check suggestions, script versions/section editing/approval, storyboard generation/editing, and narration segmentation. An AI fact-check is stored as a suggestion; only the reviewer endpoint changes a claim's verification status. Editing/regenerating a script section revokes approval and removes narration derived from changed content. Narration planning accepts only scenes linked to approved script sections.

Research search uses `SearchProvider`; JSON generation uses `AIProvider`. `none` disables either provider. Configure optional Tavily and OpenAI-compatible adapters with non-secret settings through Content Studio or `.env`. Set secrets in Windows Credential Manager using the backend's Windows account:

```powershell
keyring set GeoChronicle tavily
keyring set GeoChronicle openai
```

Secrets are not stored in SQLite or sent to React. Local review, script editing, storyboard editing, and narration planning work without provider credentials. Tests use fake adapters and do not make paid external requests.

### Project API

All routes require the existing bearer token. List queries accept `page`, `page_size`, `search`, `status`, `sort_by` (`updated_at` or `created_at`), and `sort_order` (`asc` or `desc`). Responses include page metadata and total count.

| Method | Route | Behavior |
| --- | --- | --- |
| POST | `/api/v1/projects` | Create a draft project |
| GET | `/api/v1/projects` | Search/filter/sort/paginate projects |
| GET | `/api/v1/projects/stats` | Status totals and recently updated items |
| GET | `/api/v1/projects/{project_id}` | Project details; 404 when missing |
| PATCH | `/api/v1/projects/{project_id}` | Validate and apply partial changes |
| DELETE | `/api/v1/projects/{project_id}` | Delete one project; 204 or 404 |

The React app invokes `create_project`, `list_projects`, `get_project`, `update_project`, `delete_project`, and `get_project_stats` through Rust. Rust holds the fixed loopback URL and authorization token; the webview has no direct FastAPI access.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location '..\..\apps\desktop\src-tauri'
cargo test
```

`cargo test` includes actual local Python process startup, authenticated readiness, missing/invalid token rejection, authenticated shutdown, process exit, and child reaping. Rust unit tests cover lifecycle decisions, serialization, project types, safe API errors, and port allocation. Frontend tests run from `apps/desktop` with `npm test` (Vitest and React Testing Library).

## Limitations

The Python runtime and backend are not bundled as a Tauri sidecar. Release verification currently builds an unbundled executable; installed-app backend discovery and packaging are not implemented or claimed. Research and content workflows are implemented; maps, generated media, image/speech generation, and video rendering remain out of scope.
