import { useCallback, useEffect, useState } from "react";
import { projectApi } from "./projectApi";
import { ProjectForm } from "./ProjectForm";
import type { Project, ProjectInput, ProjectQuery, ProjectStatus, ProjectUpdate } from "../../types/project";
import { projectStatusLabels } from "../../types/project";

type View = "list" | "create" | "detail" | "edit";
interface ProjectWorkspaceProps {
  initialView?: "list" | "create";
  initialProjectId?: number;
  onDataChanged: () => void;
  onOpenContent?: (project: Project) => void;
}

const defaultQuery: ProjectQuery = { page: 1, pageSize: 8, sortBy: "updated_at", sortOrder: "desc" };
const formatDate = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

export function ProjectWorkspace({ initialView = "list", initialProjectId, onDataChanged, onOpenContent }: ProjectWorkspaceProps) {
  const [view, setView] = useState<View>(initialProjectId ? "detail" : initialView);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [query, setQuery] = useState<ProjectQuery>(defaultQuery);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await projectApi.list(query);
      setProjects(response.items);
      setTotal(response.total);
      setPages(response.pages);
    } catch (reason) {
      setError(typeof reason === "string" ? reason : "Projects could not be loaded.");
    } finally { setLoading(false); }
  }, [query]);

  useEffect(() => {
    if (view === "list") void loadProjects();
  }, [view, loadProjects]);

  useEffect(() => {
    if (initialProjectId === undefined) return;
    setLoading(true);
    void projectApi.get(initialProjectId).then(project => { setSelected(project); setError(""); })
      .catch(reason => setError(typeof reason === "string" ? reason : "Project details could not be loaded."))
      .finally(() => setLoading(false));
  }, [initialProjectId]);

  async function createProject(values: ProjectInput) {
    setBusy(true); setError("");
    try {
      const project = await projectApi.create(values);
      setSelected(project); setView("detail"); onDataChanged();
    } catch (reason) { setError(typeof reason === "string" ? reason : "Project could not be created."); }
    finally { setBusy(false); }
  }

  async function openProject(project: Project) {
    setSelected(project); setView("detail"); setError("");
    try { setSelected(await projectApi.get(project.id)); }
    catch (reason) { setError(typeof reason === "string" ? reason : "Project details could not be loaded."); }
  }

  async function updateProject(values: ProjectInput & { status?: ProjectStatus }) {
    if (!selected) return;
    setBusy(true); setError("");
    const payload: ProjectUpdate = values;
    try {
      const project = await projectApi.update(selected.id, payload);
      setSelected(project); setView("detail"); onDataChanged();
    } catch (reason) { setError(typeof reason === "string" ? reason : "Project could not be updated."); }
    finally { setBusy(false); }
  }

  async function deleteProject() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      await projectApi.delete(selected.id);
      setConfirmDelete(false); setSelected(null); setView("list"); onDataChanged();
    } catch (reason) { setError(typeof reason === "string" ? reason : "Project could not be deleted."); }
    finally { setBusy(false); }
  }

  const updateQuery = (changes: Partial<ProjectQuery>) => setQuery(current => ({ ...current, ...changes, page: changes.page ?? 1 }));
  const backToList = () => { setError(""); setView("list"); };

  return <section className="content projects-content">
    <div className="projects-title-row"><div><div className="eyebrow"><span className="eyebrow-line" /> PRODUCTION WORKSPACE</div><h1>{view === "detail" ? selected?.name ?? "Project details" : view === "edit" ? "Edit project" : view === "create" ? "New project" : "Projects"}<span className="heading-period">.</span></h1><p className="welcome-subtitle">{view === "list" ? "Manage the stories you are building." : view === "detail" ? "Project brief and production settings." : "Define the scope and creative direction."}</p></div>{view === "list" && <button className="primary-button" onClick={() => { setError(""); setView("create"); }}>＋ New project</button>}</div>
    {error && <div className="inline-error" role="alert"><span>{error}</span><button className="secondary-button" onClick={() => view === "list" ? void loadProjects() : setError("")}>{view === "list" ? "Retry" : "Dismiss"}</button></div>}
    {view === "create" && <div className="project-panel"><ProjectForm busy={busy} onCancel={backToList} onSubmit={createProject} /></div>}
    {view === "edit" && selected && <div className="project-panel"><ProjectForm initial={selected} busy={busy} onCancel={() => setView("detail")} onSubmit={updateProject} /></div>}
    {view === "detail" && selected && <ProjectDetail project={selected} busy={busy} onBack={backToList} onEdit={() => setView("edit")} onDelete={() => setConfirmDelete(true)} onOpenContent={() => onOpenContent?.(selected)} />}
    {view === "list" && <>
      <div className="project-toolbar"><label className="project-search"><span>⌕</span><input value={query.search ?? ""} onChange={event => updateQuery({ search: event.target.value, page: 1 })} placeholder="Search projects or topics" aria-label="Search projects or topics" /></label><label className="filter-label"><span className="sr-only">Filter by status</span><select aria-label="Filter by status" value={query.status ?? "all"} onChange={event => updateQuery({ status: event.target.value === "all" ? undefined : event.target.value as ProjectStatus })}><option value="all">All statuses</option>{Object.entries(projectStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="filter-label"><span className="sr-only">Sort projects</span><select aria-label="Sort projects" value={`${query.sortBy}:${query.sortOrder}`} onChange={event => { const [sortBy, sortOrder] = event.target.value.split(":") as [ProjectQuery["sortBy"], ProjectQuery["sortOrder"]]; updateQuery({ sortBy, sortOrder }); }}><option value="updated_at:desc">Recently updated</option><option value="updated_at:asc">Least recently updated</option><option value="created_at:desc">Newest created</option><option value="created_at:asc">Oldest created</option></select></label><button className="secondary-button refresh-projects" onClick={() => void loadProjects()} disabled={loading}>Refresh</button></div>
      <div className="projects-count">{loading ? "Loading projects…" : `${total} ${total === 1 ? "project" : "projects"}`}</div>
      {loading ? <div className="project-cards" role="status">{Array.from({ length: 3 }, (_, index) => <div className="project-card skeleton" key={index} />)}</div> : error ? null : projects.length ? <div className="project-cards">{projects.map(project => <ProjectCard key={project.id} project={project} onOpen={() => void openProject(project)} onEdit={() => { setSelected(project); setView("edit"); }} />)}</div> : <div className="projects-empty"><div className="empty-art"><span>GC</span></div><h2>{query.search || query.status ? "No matching projects" : "No projects yet"}</h2><p>{query.search || query.status ? "Try another search or clear the status filter." : "Create a project to keep its topic and production brief in one place."}</p>{!query.search && !query.status && <button className="primary-button" onClick={() => setView("create")}>Create a project</button>}</div>}
      {!loading && pages > 1 && <div className="pagination"><span>Page {query.page} of {pages}</span><div><button className="secondary-button" disabled={query.page <= 1} onClick={() => updateQuery({ page: query.page - 1 })}>Previous</button><button className="secondary-button" disabled={query.page >= pages} onClick={() => updateQuery({ page: query.page + 1 })}>Next</button></div></div>}
    </>}
    {confirmDelete && selected && <div className="modal-backdrop" role="presentation"><section className="notice-modal delete-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-title"><button className="modal-close" onClick={() => setConfirmDelete(false)} aria-label="Cancel deletion" disabled={busy}>×</button><div className="eyebrow">DELETE PROJECT</div><h2 id="delete-title">Delete “{selected.name}”?</h2><p>This permanently removes this project and its saved brief from GeoChronicle. This cannot be undone.</p>{error && <p className="form-error" role="alert">{error}</p>}<div className="form-actions"><button className="secondary-button" onClick={() => setConfirmDelete(false)} disabled={busy}>Keep project</button><button className="danger-button" onClick={() => void deleteProject()} disabled={busy}>{busy ? "Deleting…" : "Delete project"}</button></div></section></div>}
  </section>;
}

function ProjectCard({ project, onOpen, onEdit }: { project: Project; onOpen: () => void; onEdit: () => void }) {
  return <article className="project-card"><button className="project-card-main" onClick={onOpen}><span className="project-card-art">{project.name.slice(0, 2).toUpperCase()}</span><span className="project-card-body"><span className="project-card-heading"><strong>{project.name}</strong><span className={`project-status status-${project.status}`}><i />{projectStatusLabels[project.status]}</span></span><span className="project-card-topic">{project.topic || "No topic"}</span><span className="project-card-description">{project.description || "Add a description to capture the direction of this documentary."}</span><span className="project-card-meta">Updated {formatDate(project.updated_at)}</span></span></button><button className="project-card-edit" onClick={onEdit} aria-label={`Edit ${project.name}`}>Edit</button></article>;
}

function ProjectDetail({ project, busy, onBack, onEdit, onDelete, onOpenContent }: { project: Project; busy: boolean; onBack: () => void; onEdit: () => void; onDelete: () => void; onOpenContent: () => void }) {
  return <div className="project-detail-panel"><div className="detail-actions"><button className="text-button" onClick={onBack}>← All projects</button><div><button className="primary-button" onClick={onOpenContent}>Open Content Studio →</button><button className="secondary-button" onClick={onEdit}>Edit project</button><button className="danger-button subtle-danger" onClick={onDelete} disabled={busy}>Delete</button></div></div><div className="detail-heading"><div className="project-card-art large-art">{project.name.slice(0, 2).toUpperCase()}</div><div><span className={`project-status status-${project.status}`}><i />{projectStatusLabels[project.status]}</span><h2>{project.name}</h2><p>{project.topic || "No topic added"}</p></div></div><div className="detail-description"><span className="eyebrow">PROJECT DESCRIPTION</span><p>{project.description || "No description added yet."}</p></div><dl className="detail-grid"><Detail label="Target duration" value={project.target_duration_seconds ? `${Math.floor(project.target_duration_seconds / 60)} min ${project.target_duration_seconds % 60} sec` : "Not set"} /><Detail label="Aspect ratio" value={project.aspect_ratio} /><Detail label="Language" value={project.language} /><Detail label="Visual style" value={project.visual_style.replace(/_/g, " ")} /><Detail label="Created" value={formatDate(project.created_at)} /><Detail label="Last updated" value={formatDate(project.updated_at)} /></dl><p className="scope-note">Research, fact-checking, scripts, storyboards, and narration are available in Content Studio.</p></div>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
