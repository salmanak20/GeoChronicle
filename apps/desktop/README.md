# GeoChronicle Desktop

Tauri 2 + React + TypeScript shell for the GeoChronicle Windows desktop app. The current UI is a frontend preview: project rows are sample-only, and project creation, persistence, media workflows, and AI features are not implemented.

## Development

From this directory:

```powershell
npm install
npm run typecheck
npm run build
npm run tauri dev
```

The Rust application and native WebView require the Windows prerequisites documented in the repository root README. Tauri configuration and scoped window capabilities live in `src-tauri/`.
