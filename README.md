# GeoChronicle

GeoChronicle is a local-first Windows desktop application for researching and developing geopolitical and historical documentary videos. Phase 4 adds source-grounded AI research, human-reviewed claims, versioned scripts, storyboards, and narration planning. Maps, media generation, and final video rendering are later work.

**Current status:** Phases 1–4 are implemented: local FastAPI service, authenticated typed Tauri IPC, SQLite persistence, research and source provenance, claim review, scripts, storyboards, and narration segmentation.

## Planned technology stack

- **Desktop:** Tauri 2, Rust, React, TypeScript, Vite, Tailwind CSS, Zustand
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, SQLite, Alembic, Pydantic, WebSockets
- **Media:** FFmpeg, FFprobe, MapLibre GL, GeoJSON, replaceable AI image and text-to-speech providers
- **Quality:** Pytest, Vitest, React Testing Library, Ruff, TypeScript checks

The repository includes an implemented subset of this stack; see phase notes below for current scope.

## Architecture overview

The planned application is a local-first modular monolith. The Tauri desktop shell owns the native window and operating-system integration. React/TypeScript provides the production interface. A separately packaged local FastAPI process owns application workflows, persistence, jobs, provider adapters, and render orchestration. The frontend/backend boundary and proposed local communication are described in [ARCHITECTURE.md](ARCHITECTURE.md).

Projects and research records stay on the user's machine. AI capabilities use replaceable provider adapters; secrets are read server-side from Windows Credential Manager through Python keyring and are not stored in SQLite, source files, or logs. Remote providers receive the topic and source excerpts submitted for the requested operation.

## Repository layout

```text
apps/desktop/       Tauri 2 + React desktop shell
services/backend/   Future Python API and application services
packages/contracts/ Shared API and data contracts
config/             Development and application configuration templates
resources/          Development resources
scripts/            Maintainer and developer scripts
tests/              Automated tests, organized by component as they are added
docs/               Supplementary project documentation
```

The milestone documents live at the repository root. The desktop application is under `apps/desktop/`; the local API, project-management workflows, and database are under `services/backend/`.

## Development prerequisites

Environment audit performed on 2026-11-24 (Windows 11 x64):

| Tool | Detected | Result |
| --- | --- | --- |
| Windows | Windows 11 Pro, build 26300 | Present |
| PowerShell | 7.6.9 | Present |
| Git | 2.54.0.windows.1 | Present |
| Node.js / npm | 26.13.0 / 11.20.0 | Present; updated for desktop implementation |
| Rust / Cargo | 1.99.1 / 1.99.1, stable MSVC x64 toolchain | Present |
| Python | 3.12.10 (only Python installation found) | Required minor version present; update to a current 3.12 patch before backend work |
| FFmpeg / FFprobe | 9.0.2 full build | Present |
| Visual Studio Build Tools | VS 2022, MSVC 14.44.35207, Windows SDK 10.0.26100.0 | Present |
| Microsoft Edge WebView2 Runtime | 158.0.4370.33 | Present |

`python3` resolves to the Microsoft Store execution alias and does not launch an interpreter in this shell; use `python` or the `py` launcher. Node.js 26 is an LTS line, but the detected 26.2.0 is behind 26.13.0 LTS (released 2026-10-28); update to a current Node 26 patch before frontend implementation. Python 3.12.10 is the last 3.12 release with an official Windows installer. Python 3.12.16 is the current 3.12 security release and is source-only, so arrange a supported patched 3.12 runtime before backend implementation. See the [Python 3.12.16 release notes](https://www.python.org/downloads/release/python-31216/). Environment versions can change; rerun the checks when setting up another machine.

Tauri's current Windows prerequisites include the Microsoft C++ Build Tools and WebView2 Runtime. Both were found in this environment. See the [Tauri Windows prerequisites](https://v2.tauri.app/start/prerequisites/) and [Node.js release schedule](https://nodejs.org/en/about/previous-releases/).

## Initial setup

The repository workspace is `S:\Projects\GeoChronicle`. In PowerShell:

```powershell
Set-Location 'S:\Projects\GeoChronicle'
git status --short --branch
```

The desktop shell dependencies are declared in `apps/desktop/package.json` and locked in its npm lock file. From that directory, run `npm install`, `npm run typecheck`, `npm run build`, and `npm run tauri dev`. Rust dependencies are resolved from `apps/desktop/src-tauri/Cargo.toml` during Cargo checks/builds. Python dependencies are listed in `services/backend/requirements.txt`; use its repo-local `.venv`. Keep environment-specific settings in an untracked `.env` file based on `.env.example`; never put real credentials in that file.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Development guidelines](DEVELOPMENT-GUIDELINES.md)
- [Development log and environment audit](DEVELOPMENT-LOG.md)
- [Example local configuration](.env.example)



## Desktop shell

The current app provides a data-backed dashboard and project workflows (create, browse, search, filter, sort, paginate, view, edit, and delete), plus the Phase 4 Content Studio. Create Video, Media Library, and Templates remain explicitly labeled placeholders. Native app development requires the Tauri Windows prerequisites listed above.

## Phase 4: research and content intelligence

Content Studio supports research sessions with deduplicated source provenance, claims linked to source evidence, reviewer-controlled claim status, AI fact-check suggestions, structured script drafts and versions, per-section edits/regeneration, storyboard scenes linked to script sections and researched IDs, and sentence-level narration planning with paragraph indexes and duration estimates. Script edits invalidate approval and dependent narration. Narration requires approved linked script sections.

Tavily search and OpenAI-compatible JSON generation are optional adapters. Configure provider IDs/endpoints/model in the app or `.env`; install secrets with `keyring set GeoChronicle tavily` and `keyring set GeoChronicle openai`. Without credentials, local review/editing workflows remain available. See [backend setup](services/backend/README.md). Migration `0003_content_intelligence` adds the new tables while preserving existing projects. The Python backend is not bundled into a release executable.


## Phase 2 backend foundation

A local FastAPI service, SQLite models, Alembic migrations, authenticated lifecycle, and project-management API are implemented under `services/backend/`. Start the native development app from `apps/desktop` with `npm run tauri dev`; Rust launches and supervises the local Python virtualenv backend. The Python sidecar is not bundled or installed with the release executable. See [backend setup](services/backend/README.md).

## Phase 3: project management

Projects persist in `%LOCALAPPDATA%\GeoChronicle\geochronicle.db`. The API supports authenticated project create/list/get/partial-update/delete and project statistics. Listing supports pagination, name/topic search, status filters, and updated/created sorting. React calls typed Tauri commands; Rust owns the backend URL and launch token.

Project fields are name (required, up to 200 characters), optional topic (500), description (5,000), target duration (30–7,200 seconds), aspect ratio, language, visual style, lifecycle status, and UTC creation/update timestamps. Status values are `draft`, `in_progress`, `completed`, and `archived`. Alembic migration `0002_project_management` adds the production settings fields and topic/status constraints/index while preserving existing project rows.

Run the desktop tests from `apps/desktop`: `npm test`, `npm run typecheck`, `npm run build`, and `npm audit --audit-level=low`. Run backend tests from `services/backend` with `.\.venv\Scripts\python.exe -m pytest -q`; run migration checks with `.\.venv\Scripts\alembic.exe check`. Run Rust checks from `apps/desktop/src-tauri` with `cargo fmt -- --check`, `cargo check`, and `cargo test`. A Tauri dev run requires both Node dependencies and the repository-local Python virtual environment. There is no installer or packaged Python sidecar yet.
