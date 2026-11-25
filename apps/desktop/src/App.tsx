import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Dashboard } from "./features/dashboard/Dashboard";
import { ProjectWorkspace } from "./features/projects/ProjectWorkspace";
import { ContentWorkspace } from "./features/content/ContentWorkspace";
import type { Project } from "./types/project";
import "./App.css";

type Page = "Dashboard" | "Projects" | "Content Studio" | "Create Video" | "Media Library" | "Templates" | "Settings";
type BackendStatus = { state: "starting" | "ready" | "stopping" | "stopped" | "error"; database_ready: boolean; error: string | null };
const navigation: { label: Page; icon: string }[] = [
  { label: "Dashboard", icon: "grid" }, { label: "Projects", icon: "folder" },
  { label: "Content Studio", icon: "spark" },
  { label: "Create Video", icon: "spark" }, { label: "Media Library", icon: "image" },
  { label: "Templates", icon: "layers" }, { label: "Settings", icon: "settings" },
];
const backendLabel = (state: BackendStatus["state"]) => ({ starting: "Starting", ready: "Connected", stopping: "Stopping", stopped: "Disconnected", error: "Error" })[state];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, string> = { grid: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z", folder: "M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", spark: "m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 14l1 2.5 2 1-2 1-1 2.5-1-2.5-2-1 2-1z", image: "M4 4h16v16H4z M4 16l5-5 4 4 3-3 4 4 M15 9h.01", layers: "m12 3 9 5-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5", settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.6 2.8-.2-.1a1.7 1.7 0 0 0-1.8.1l-.2.1h-3.2l-.1-.2a1.7 1.7 0 0 0-1.5-1l-.2-.1-2.8-1.6.1-.2a1.7 1.7 0 0 0-.1-1.8l-.1-.2v-3.2l.2-.1a1.7 1.7 0 0 0 1-1.5l.1-.2 1.6-2.8.2.1a1.7 1.7 0 0 0 1.8-.1l.2-.1h3.2l.1.2a1.7 1.7 0 0 0 1.5 1l.2.1 2.8 1.6-.1.2a1.7 1.7 0 0 0 .1 1.8l.1.2v3.2z" };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.grid} /></svg>;
}
function BrandMark() { return <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>; }

function App() {
  const [backend, setBackend] = useState<BackendStatus>({ state: "starting", database_ready: false, error: null });
  const [page, setPage] = useState<Page>("Dashboard");
  const [projectMode, setProjectMode] = useState<"list" | "create">("list");
  const [projectId, setProjectId] = useState<number | undefined>();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [revision, setRevision] = useState(0);
  const refreshBackend = () => invoke<BackendStatus>("backend_status").then(setBackend).catch(() => setBackend({ state: "error", database_ready: false, error: "Backend status unavailable" }));
  const retryBackend = () => { setBackend({ state: "starting", database_ready: false, error: null }); void invoke<BackendStatus>("retry_backend").then(setBackend).catch(error => setBackend({ state: "error", database_ready: false, error: typeof error === "string" ? error : "Backend could not start" })); };
  useEffect(() => { void refreshBackend(); const timer = window.setInterval(() => void refreshBackend(), 5000); return () => window.clearInterval(timer); }, []);

  const openNewProject = () => { setPage("Projects"); setProjectMode("create"); setProjectId(undefined); };
  const openProjects = () => { setPage("Projects"); setProjectMode("list"); setProjectId(undefined); };
  const openProject = (project: Project) => { setPage("Projects"); setProjectMode("list"); setProjectId(project.id); };
  const openContentForProject = (project: Project) => { setProjectId(project.id); setPage("Content Studio"); };
  const goToPage = (next: Page) => { setPage(next); if (next === "Projects") { setProjectMode("list"); setProjectId(undefined); } };

  return <div className={`app-shell${theme === "light" ? " light-theme" : ""}`}>
    <aside className="sidebar">
      <button className="brand" onClick={() => goToPage("Dashboard")} aria-label="GeoChronicle home"><BrandMark /><span className="brand-copy"><strong>GeoChronicle</strong><small>STUDIO</small></span></button>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">{navigation.map(item => <button key={item.label} className={`nav-item${page === item.label ? " active" : ""}`} onClick={() => goToPage(item.label)} aria-current={page === item.label ? "page" : undefined}><Icon name={item.icon} /><span>{item.label}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="storage-card"><div className="storage-icon"><Icon name="folder" /></div><div><strong>GeoChronicle</strong><span>Local workspace</span></div><span className={`online-dot${backend.state !== "ready" ? " offline" : ""}`} /></div><button className="profile" onClick={() => goToPage("Settings")}><div className="avatar">GC</div><span><strong>Creator workspace</strong><small>Local profile</small></span><Icon name="settings" /></button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{page}</strong></div><div className="top-actions"><button className="status-pill" onClick={() => void refreshBackend()} title={backend.error || "Refresh backend status"}><i className={`status-${backend.state}`} /> Backend {backend.state === "ready" ? `connected · DB ${backend.database_ready ? "ready" : "unavailable"}` : backendLabel(backend.state)}</button><button className="icon-button theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme" title="Toggle theme">◐</button><button className="top-avatar" onClick={() => goToPage("Settings")} aria-label="Open settings">GC</button></div></header>
      {page === "Dashboard" && <Dashboard key={revision} onCreate={openNewProject} onOpenProject={openProject} onViewProjects={openProjects} />}
      {page === "Projects" && <ProjectWorkspace key={`${projectMode}:${projectId ?? "none"}`} initialView={projectMode} initialProjectId={projectId} onDataChanged={() => setRevision(value => value + 1)} onOpenContent={openContentForProject} />}
      {page === "Content Studio" && <ContentWorkspace key={projectId ?? "choose-project"} projectId={projectId} onSelectProject={openContentForProject} onBack={() => projectId ? openProject({ id: projectId } as Project) : openProjects()} />}
      {page === "Settings" && <Settings backend={backend} refresh={refreshBackend} retry={retryBackend} />}
      {page !== "Dashboard" && page !== "Projects" && page !== "Settings" && <Placeholder page={page} onBack={() => goToPage("Dashboard")} onCreate={openNewProject} />}
      <footer className="app-footer"><span><BrandMark /> GeoChronicle <i /> Local project workspace</span><span>PHASE 4 <b>·</b> CONTENT INTELLIGENCE</span></footer>
    </main>
  </div>;
}

function Settings({ backend, refresh, retry }: { backend: BackendStatus; refresh: () => Promise<void>; retry: () => void }) {
  return <section className="content placeholder-content"><div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE</div><h1>Settings<span className="heading-period">.</span></h1><p className="welcome-subtitle">Local application and backend status.</p><div className="settings-status"><div className="section-heading"><div><h2>Local backend</h2><p>Connection and database status for this desktop session.</p></div><button className="secondary-button" onClick={() => void refresh()}>Refresh status</button></div><div className="settings-status-row"><span className={`state-indicator ${backend.state}`} /><div><strong>{backendLabel(backend.state)}</strong><small>Database {backend.database_ready ? "ready" : "not ready"}</small></div>{(backend.state === "error" || backend.state === "stopped") && <button className="secondary-button" onClick={retry}>Retry backend</button>}</div>{backend.error && <p className="settings-error" role="status">{backend.error}</p>}<p className="settings-note">Backend credentials and internal diagnostics are not shown here.</p></div></section>;
}

function Placeholder({ page, onBack, onCreate }: { page: Page; onBack: () => void; onCreate: () => void }) {
  const descriptions: Record<"Create Video" | "Media Library" | "Templates", string> = {
    "Create Video": "Video generation is not implemented in this phase. Your project brief is ready to build on.",
    "Media Library": "Media importing and asset management are planned for a later phase.",
    Templates: "Documentary templates are not available yet.",
  };
  return <section className="content placeholder-content"><div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE</div><h1>{page}<span className="heading-period">.</span></h1><div className="empty-state"><div className="empty-art"><BrandMark /></div><h2>{page === "Create Video" ? "Project management comes first" : "This workspace is reserved"}</h2><p>{descriptions[page as keyof typeof descriptions]}</p>{page === "Create Video" ? <button className="primary-button" onClick={onCreate}>Create a project</button> : <button className="secondary-button" onClick={onBack}>Back to dashboard</button>}</div></section>;
}

export default App;
