# GeoChronicle Architecture

## Status

This document records the intended architecture and the implemented Phase 1–3 foundation. Features not listed as implemented remain planned.

## System shape

GeoChronicle will begin as a modular monolith split across two local processes:

1. **Desktop process:** Tauri 2 and Rust provide the native Windows window, app lifecycle, scoped filesystem access, operating-system integration, and startup/shutdown of the backend sidecar. React, TypeScript, Vite, Tailwind CSS, and Zustand provide the user interface and its presentation state.
2. **Backend process:** A separately packaged Python 3.12 process using FastAPI owns product workflows, validation, project metadata, persistent jobs, provider adapters, and render orchestration. SQLAlchemy 2 and SQLite provide local persistence; Alembic manages schema changes; Pydantic validates API payloads.

The modules should remain in one product repository and be separated by explicit interfaces. Split into services only if product needs make that complexity worthwhile.

## Desktop/backend communication

Rust starts and supervises the Python sidecar and stops it when the desktop application exits. React requests domain operations through Tauri IPC; Rust sends typed requests to the local versioned FastAPI API, keeping the backend URL and launch token out of the webview. WebSockets are reserved for future job progress. The API contract is represented by Pydantic schemas, Rust IPC types, and matching TypeScript interfaces.

The service is local-only: it binds to loopback and uses a per-launch secret for backend requests. The OS-assigned port is managed by Rust. Tauri exposes only the default core capability; no general filesystem or shell access is granted.

## Persistence and project files

- Store application settings, project catalog metadata, and durable job state in SQLite under the current user's application-data directory.
- Use Alembic migrations for database schema changes. Do not edit a production database schema by hand.
- Keep each user's project and media assets under a dedicated project directory at a user-selected local path. Keep generated assets, intermediate files, and final exports organized within that project, with clear cleanup/recovery rules.
- Store only references and metadata in SQLite when large binary files belong in the project directory. Resolve and validate paths at the backend boundary.
- Keep user data local by default. Any future sync or upload behavior must be an explicit product feature.

Project catalog metadata is stored in the `projects` SQLite table. Project assets and generated files are not implemented in this phase.

## Background jobs and recovery

Long-running generation and rendering operations will run as persistent backend jobs instead of blocking API requests. Persist job type, state, progress, timestamps, safe error details, and recovery information. On restart, reconcile interrupted work and resume or mark it failed according to the operation's idempotency and available checkpoints. Send progress over WebSockets while keeping SQLite as the source of truth.

## AI provider adapters

Define narrow adapter interfaces for text generation, image generation, and speech synthesis. A capability-level router can select among configured providers so the product can use a hybrid strategy and replace providers without changing application workflows. Validate provider responses before storing or passing them to other stages. Apply bounded retries and timeouts only where operations are safe to retry.

Never place provider secrets in source code, frontend bundles, project documents, databases, or logs. Future secret access should go through Windows Credential Manager (or an equivalent OS-backed credential facility) and should remain server-side. Provider integration is not part of the current milestone.

## Maps and media rendering

Map scenes will use MapLibre GL with validated GeoJSON and documented geographic datasets. The backend will coordinate scene and narration assets and invoke FFmpeg locally for composition, audio mixing, subtitle integration, and export. Use FFprobe to inspect inputs and validate completed outputs. Invoke media tools with argument arrays (not interpolated shell commands), validate paths and options, capture progress, and surface actionable errors without logging sensitive data.

Map capture, scene timing, codecs, export presets, and dataset licensing will be decided and tested during media-focused milestones. No renderer or media pipeline exists yet.

## Security and operations

- No hardcoded API keys; never commit `.env` files or private credentials.
- Use Windows Credential Manager for future provider secrets.
- Bind local services to loopback and authenticate the desktop/backend session.
- Validate all external and inter-process input, including file paths, GeoJSON, and provider responses.
- Use structured logs with secret and personal-data redaction.
- Keep local projects in dedicated directories and apply explicit Tauri filesystem capabilities.
- Use bounded retries, timeouts, cleanup, and durable job recovery where appropriate.

These are architectural constraints for later implementation, not claims about current controls.

## Phase 2 implementation (local development)

The current development build implements the Tauri 2 + React shell and a local FastAPI health service. Rust owns the spawned Python `Child`, loopback port, and per-launch random token. The port is selected by binding `127.0.0.1:0` and reading the assigned port. Windows socket-handle transfer to Uvicorn is not used: the listener is released before Python binds, so a short allocation race remains. To contain it, startup retries up to four times when the exact launched child exits before authenticated readiness; startup never treats an unauthenticated listener as the backend. Retry exhaustion moves lifecycle state to Error with a non-sensitive message.

Lifecycle state is managed by the Tauri process: Starting, Ready, Stopping, Stopped, and Error. Startup runs outside the UI event loop; one manager owns at most one child. The Settings page obtains status and invokes a retry command through Tauri IPC. Health and readiness HTTP calls carry the token only in Rust. The token is set in the child environment, required on health/readiness and the internal shutdown endpoint, and held only for the owned process lifetime. React receives status fields and safe error text, never credentials or token material.

Backend stdout and stderr are appended to `%LOCALAPPDATA%/GeoChronicle/logs/backend.log` (or a temporary-directory fallback if `LOCALAPPDATA` is unavailable). API tokens are not logged.

Normal Tauri exit sends authenticated `POST /api/v1/internal/shutdown`, waits up to five seconds for the exact child, then force-kills and waits/reaps only that `Child` if needed. Repeated shutdown is safe. A launch timeout is bounded to 20 seconds, with at most four launch attempts. Process-tree termination is intentionally not used. The lifecycle behavior and actual Python process integration are covered by Rust tests.

Backend startup configures SQLite at `%LOCALAPPDATA%/GeoChronicle/geochronicle.db` by default and applies Alembic migrations. Tests use temporary SQLite files. Migration downgrade/upgrade is covered. The bundled/installed application does not yet package the Python runtime or backend sidecar; native release packaging remains a development executable only.

## Phase 3 implementation: project management

The backend owns project validation, persistence, filtering, sorting, and aggregate statistics. Alembic revision `0002_project_management` adds optional production settings (`target_duration_seconds`, `aspect_ratio`, `language`, `visual_style`), a topic index, and a valid-status constraint while retaining the integer project IDs from Phase 2. Project request/response schemas validate bounded text, language tags, aspect ratios, durations, and four lifecycle statuses. API routes require the existing per-launch authentication.

Rust provides fixed-origin typed commands for create/list/get/update/delete/statistics. A tri-state patch type distinguishes an omitted field from an explicit null for nullable values. React accesses the service only through these commands. Dashboard statistics and recent projects are loaded from SQLite; Projects supports browse, search, status filtering, sorting, pagination, details, edits, and a delete confirmation. Create Video, Media Library, and Templates remain placeholders.

The desktop release is still unbundled: `npm run tauri build -- --no-bundle` validates the Windows executable but does not package/install the Python runtime or backend. No AI, map, generated asset, audio/video, or rendering workflow is part of Phase 3.
