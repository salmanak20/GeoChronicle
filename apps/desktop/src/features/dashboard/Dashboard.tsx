import { useCallback, useEffect, useState } from "react";
import { projectApi } from "../projects/projectApi";
import type { Project, ProjectStats } from "../../types/project";
import { projectStatusLabels } from "../../types/project";

interface DashboardProps {
  onCreate: () => void;
  onOpenProject: (project: Project) => void;
  onViewProjects: () => void;
}

const dateLabel = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));

export function Dashboard({ onCreate, onOpenProject, onViewProjects }: DashboardProps) {
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setStats(await projectApi.stats()); }
    catch (reason) { setError(typeof reason === "string" ? reason : "Project summary could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <section className="content dashboard-content">
    <div className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" /> YOUR CREATIVE WORKSPACE</div><h1>Good morning, creator<span className="heading-period">.</span></h1><p className="welcome-subtitle">Your next story is waiting to be told.</p></div><button className="primary-button" onClick={onCreate}>＋ New project</button></div>
    {error && <div className="inline-error" role="alert"><span>{error}</span><button className="secondary-button" onClick={() => void load()}>Retry</button></div>}
    <div className="stats-grid" aria-label="Project statistics">
      <StatCard title="Total projects" value={stats?.total} loading={loading} foot="Saved in your workspace" />
      <StatCard title="In progress" value={stats?.in_progress} loading={loading} foot="Stories underway" />
      <StatCard title="Completed" value={stats?.completed} loading={loading} foot="Marked complete by you" />
      <StatCard title="Drafts" value={stats?.draft} loading={loading} foot="Ready when you are" />
    </div>
    <div className="section-heading"><div><h2>Recently updated</h2><p>Projects saved on this device</p></div><button className="text-button" onClick={onViewProjects}>All projects <span aria-hidden="true">→</span></button></div>
    {loading ? <div className="project-loading" role="status">Loading your projects…</div> : error ? null : stats?.recently_updated.length ? <div className="project-list">{stats.recently_updated.map(project => <button className="project-row" key={project.id} onClick={() => onOpenProject(project)}><span className="project-art sand"><span>{project.name.slice(0, 2).toUpperCase()}</span></span><span className="project-info"><strong>{project.name}</strong><span>{project.topic || project.description || "No topic added"}</span></span><span className="project-date">{dateLabel(project.updated_at)}</span><span className={`project-status status-${project.status}`}><i />{projectStatusLabels[project.status]}</span><span className="row-more">→</span></button>)}</div> : <div className="dashboard-empty"><div className="empty-art"><span>GC</span></div><h2>Your first story starts here</h2><p>Create a project to keep its topic, format and production details together.</p><button className="primary-button" onClick={onCreate}>Create your first project</button></div>}
    <div className="section-heading quick-heading"><div><h2>Quick actions</h2><p>Start with the foundation of your next documentary</p></div></div>
    <div className="quick-grid"><button className="quick-card" onClick={onCreate}><span className="quick-icon gold">＋</span><span><strong>Start a project</strong><small>Define the topic and creative format</small></span><span>→</span></button><button className="quick-card" onClick={onViewProjects}><span className="quick-icon slate">▤</span><span><strong>Browse projects</strong><small>Search, filter and manage saved work</small></span><span>→</span></button></div>
  </section>;
}

function StatCard({ title, value, loading, foot }: { title: string; value?: number; loading: boolean; foot: string }) {
  return <article className="stat-card"><div className="stat-top"><span>{title}</span></div><div className="stat-value">{loading ? <span className="stat-loading">···</span> : value ?? 0}</div><div className="stat-foot">{foot}</div></article>;
}
