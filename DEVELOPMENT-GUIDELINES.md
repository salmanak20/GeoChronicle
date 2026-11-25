# Development Guidelines

These rules apply to the implemented Phase 1–3 foundation and later phases. The current repository includes the Tauri UI, local FastAPI lifecycle management, SQLite persistence, and project CRUD.

## Coding standards

- Use TypeScript with strict type checking for the React application; keep UI, state, and API access responsibilities clear.
- Use idiomatic Rust and explicit Tauri capabilities. Keep native commands narrow and validate arguments at the boundary.
- Use Python 3.12, type hints, Pydantic request/response models, SQLAlchemy 2, Ruff, and structured logging in the backend.
- Prefer small cohesive modules and explicit interfaces. Keep the initial deployment a modular monolith; avoid speculative abstraction and premature service splits.
- Keep backend and frontend contracts versioned and aligned. Do not duplicate business rules across layers.
- Use replaceable adapters for each external AI capability. Keep provider-specific details inside adapters.
- Avoid adding dependencies unless they address a concrete need; record non-obvious architecture or dependency decisions.

## Testing and quality

- Add tests with each behavior: Pytest for backend units/integration, Vitest and React Testing Library for frontend behavior, and Rust tests for native logic where appropriate.
- Keep tests deterministic and local by default. Mock provider boundaries in tests; never send real paid API requests as part of routine test suites.
- Run relevant tests, Ruff, TypeScript checks, and builds after changes. Report commands and actual outcomes; do not infer success from a command being started.
- Add migration tests for SQLite schema changes and recovery tests for persistent jobs.

## Desktop backend lifecycle

- Rust is the sole owner of the backend child process, local port, and per-launch token. Never discover or terminate a backend by process name or PID search.
- Bind services to loopback only. The current Windows launcher releases the OS-assigned port before Python binds; therefore detect child startup collisions, retry a bounded number of times, and require authenticated readiness before marking the service Ready. Never connect to an unverified local listener.
- Keep backend authentication tokens in Rust and the child process environment. Do not pass them to React, include them in status/error payloads, or log them.
- On desktop exit, request token-authenticated shutdown, wait a bounded interval for the exact owned child, then force-terminate and reap only that child. Make shutdown idempotent.
- Model startup, readiness, shutdown, crash, error, and retry transitions explicitly. UI status must come from Tauri IPC and contain safe messages only.
- Run Alembic migrations at backend startup. Tests should use isolated temporary databases and should include real process integration where the lifecycle crosses process boundaries.
- Never edit persisted schema outside an Alembic migration. Preserve existing Phase 2 rows and verify both migration directions on disposable test databases.
- Route project API calls through typed Tauri IPC; React must never receive the backend token or choose an arbitrary backend URL.
- Do not claim test coverage for untested paths.

## Architecture and persistence

- Keep UI presentation in React, OS integration and lifecycle in Tauri/Rust, and domain workflows/persistence/jobs in Python services.
- Keep modules replaceable behind documented interfaces while retaining one local product deployment.
- Use SQLite with Alembic migrations. Never modify a database schema outside a migration after persistence is in use.
- Keep each project's user data and generated media within dedicated project directories. Resolve paths safely and avoid writing user data into the source tree.
- Make long operations durable and observable. Use checkpoints, bounded retries, timeouts, and cleanup appropriate to each operation.
- Use FFmpeg locally for final video rendering. Invoke subprocesses with argument arrays and validate all inputs.

## Security and privacy

- Never hardcode API keys, tokens, passwords, or private certificates. Never commit `.env` files or credentials.
- Use Windows Credential Manager or a suitable OS-backed facility for future provider secrets; expose only provider selection and non-secret settings to the frontend.
- Do not log credentials, authorization headers, private prompts, or sensitive user data. Redact exceptions from external providers before logging.
- Validate all user input, inter-process messages, GeoJSON, file paths, and external API responses.
- Bind the future backend to loopback only, authenticate its local client, validate origins, and expose no unnecessary local/network service.
- Keep Tauri filesystem and shell capabilities limited to the paths and operations required by the feature.
- Handle errors explicitly; return safe actionable messages to the user and preserve detailed structured diagnostics without secrets.

## Git workflow

- Work on the specified feature branch and inspect `git status` before editing.
- Keep commits focused and separate by completed milestone when commits are authorized. Do not amend, rewrite existing commits, or push without explicit instruction.
- Never include local databases, renders, generated assets, credentials, secrets, or machine-specific IDE settings in a commit.
- Review the staged diff and run the relevant checks before each authorized commit.
