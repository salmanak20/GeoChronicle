import { useCallback, useEffect, useMemo, useState } from "react";
import { projectApi } from "../projects/projectApi";
import type { Project } from "../../types/project";
import type { Claim, FactCheck, NarrationSegment, ProviderStatus, ResearchSession, ResearchSource, Scene, ScriptDocument, Storyboard } from "../../types/content";
import { contentApi, errorMessage } from "./contentApi";
import "./content.css";

type Tab = "Research" | "Fact-check" | "Script" | "Storyboard" | "Narration";
const tabs: Tab[] = ["Research", "Fact-check", "Script", "Storyboard", "Narration"];
const verificationLabels: Record<string, string> = { unverified: "Unverified", supported: "Supported", partially_supported: "Partially supported", disputed: "Disputed", contradicted: "Contradicted", insufficient_evidence: "Insufficient evidence" };
const emptyProviders: ProviderStatus = { search_provider: "none", search_endpoint: "https://api.tavily.com/search", search_available: false, ai_provider: "none", ai_endpoint: "https://api.openai.com/v1/chat/completions", ai_model: "gpt-4o-mini", ai_available: false, credentials_store: "Windows Credential Manager" };

export function ContentWorkspace({ projectId, onSelectProject, onBack }: { projectId?: number; onSelectProject?: (project: Project) => void; onBack: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<Tab>("Research");
  const [providers, setProviders] = useState<ProviderStatus>(emptyProviders);
  const [searchProvider, setSearchProvider] = useState("none");
  const [searchEndpoint, setSearchEndpoint] = useState(emptyProviders.search_endpoint);
  const [aiProvider, setAiProvider] = useState("none");
  const [aiEndpoint, setAiEndpoint] = useState(emptyProviders.ai_endpoint);
  const [aiModel, setAiModel] = useState(emptyProviders.ai_model);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [sources, setSources] = useState<ResearchSource[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [scripts, setScripts] = useState<ScriptDocument[]>([]);
  const [script, setScript] = useState<ScriptDocument | null>(null);
  const [versions, setVersions] = useState<Array<{ id: number; version_number: number; change_note: string; created_at: string }>>([]);
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [narration, setNarration] = useState<NarrationSegment[]>([]);
  const [selectedSource, setSelectedSource] = useState<ResearchSource | null>(null);
  const [sourceLimit, setSourceLimit] = useState(8);
  const [region, setRegion] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [claimNotes, setClaimNotes] = useState<Record<number, string>>({});
  const [claimChecks, setClaimChecks] = useState<Record<number, FactCheck[]>>({});
  const [draftSections, setDraftSections] = useState<Record<string, string>>({});
  const [draftScenes, setDraftScenes] = useState<Record<number, Scene>>({});
  const [draftNarration, setDraftNarration] = useState<Record<number, string>>({});
  const [speechRate, setSpeechRate] = useState(145);

  const loadProjectData = useCallback(async (id: number) => {
    setLoading(true); setError("");
    try {
      const [projectInfo, providerInfo, researchSessions, savedScripts] = await Promise.all([
        projectApi.get(id), contentApi.providers(), contentApi.researchSessions(id), contentApi.scripts(id),
      ]);
      setProject(projectInfo); setProviders(providerInfo); setSearchProvider(providerInfo.search_provider); setSearchEndpoint(providerInfo.search_endpoint); setAiProvider(providerInfo.ai_provider); setAiEndpoint(providerInfo.ai_endpoint); setAiModel(providerInfo.ai_model); setSessions(researchSessions); setScripts(savedScripts);
      const recent = researchSessions[0];
      setSession(recent ?? null);
      const latestScript = savedScripts[0];
      setScript(latestScript ? await contentApi.script(latestScript.id) : null);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }, []);

  const loadResearchDetails = useCallback(async (id: number) => {
    const [sourceRows, claimRows] = await Promise.all([contentApi.sources(id), contentApi.claims(id)]);
    setSources(sourceRows); setClaims(claimRows);
    const checks = await Promise.all(claimRows.map(async claimRow => [claimRow.id, await contentApi.factCheckResults(claimRow.id)] as const));
    setClaimChecks(Object.fromEntries(checks));
  }, []);

  useEffect(() => {
    if (projectId !== undefined) { void loadProjectData(projectId); return; }
    setLoading(true);
    void projectApi.list({ page: 1, pageSize: 100, sortBy: "updated_at", sortOrder: "desc" })
      .then(response => setProjects(response.items)).catch(reason => setError(errorMessage(reason))).finally(() => setLoading(false));
  }, [projectId, loadProjectData]);

  const refreshResearch = useCallback(async (current: ResearchSession) => {
    const next = await contentApi.researchStatus(current.id);
    setSession(next);
    setSessions(items => items.map(item => item.id === next.id ? next : item));
    if (next.status === "completed") {
      await loadResearchDetails(next.id);
    }
    return next;
  }, [loadResearchDetails]);

  useEffect(() => {
    if (!session) { setSources([]); setClaims([]); return; }
    let active = true;
    const poll = async () => {
      try {
        const next = await contentApi.researchStatus(session.id);
        if (!active) return;
        setSession(next); setSessions(items => items.map(item => item.id === next.id ? next : item));
        if (next.status === "completed") {
          if (active) await loadResearchDetails(next.id);
        }
      } catch (reason) { if (active) setError(errorMessage(reason)); }
    };
    void poll();
    if (session.status === "pending" || session.status === "running") {
      const timer = window.setInterval(() => void poll(), 2500);
      return () => { active = false; window.clearInterval(timer); };
    }
    return () => { active = false; };
  }, [session?.id, session?.status, refreshResearch, loadResearchDetails]);

  useEffect(() => {
    if (!script) { setStoryboards([]); setStoryboard(null); return; }
    let active = true;
    void Promise.all([contentApi.versions(script.id), contentApi.storyboards(script.id)]).then(([versionRows, boards]) => {
      if (active) { setVersions(versionRows); setStoryboards(boards); setStoryboard(boards[0] ?? null); }
    }).catch(reason => { if (active) setError(errorMessage(reason)); });
    return () => { active = false; };
  }, [script?.id]);

  useEffect(() => {
    if (!storyboard) { setNarration([]); return; }
    void contentApi.narration(storyboard.id).then(setNarration).catch(reason => setError(errorMessage(reason)));
  }, [storyboard?.id]);

  async function run(action: () => Promise<unknown>, done?: (value: any) => void | Promise<void>, message?: string) {
    setBusy(true); setError(""); setSuccess("");
    try { const result = await action(); await done?.(result); if (message) setSuccess(message); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function startResearch() {
    if (!project) return;
    await run(() => contentApi.startResearch(project.id, project.topic ?? "", sourceLimit, region, dateRange), async result => {
      const newSession = result as ResearchSession;
      setSession(newSession); setSessions(items => [newSession, ...items]); setSources([]); setClaims([]); setTab("Research");
      await refreshResearch(newSession);
    }, "Research queued. Results will appear here as the providers finish.");
  }

  async function saveProviderSettings() {
    await run(() => contentApi.saveProviderConfiguration({ searchProvider, searchEndpoint, aiProvider, aiEndpoint, aiModel }), value => {
      const next = value as ProviderStatus;
      setProviders(next); setSearchProvider(next.search_provider); setSearchEndpoint(next.search_endpoint); setAiProvider(next.ai_provider); setAiEndpoint(next.ai_endpoint); setAiModel(next.ai_model);
    }, "Provider configuration saved. Credentials are managed separately in Windows Credential Manager.");
  }

  async function selectResearch(id: number) {
    const next = sessions.find(item => item.id === id);
    if (!next) return;
    setSession(next); setSelectedSource(null); setError("");
    if (next.status === "completed") {
      try { await loadResearchDetails(id); }
      catch (reason) { setError(errorMessage(reason)); }
    }
  }

  async function openScript(saved: ScriptDocument) {
    await run(() => contentApi.script(saved.id), next => { setScript(next as ScriptDocument); setDraftSections({}); setTab("Script"); });
  }

  async function saveSection(sectionKey: string) {
    if (!script) return;
    await run(() => contentApi.saveSection(script.id, sectionKey, draftSections[sectionKey] ?? ""), async value => {
      const next = value as ScriptDocument; setScript(next); setDraftSections({}); setScripts(items => items.map(item => item.id === next.id ? next : item));
      setVersions(await contentApi.versions(next.id));
    }, "Script section saved as a new version.");
  }

  async function setSectionApproval(sectionKey: string, approved: boolean) {
    if (!script) return;
    await run(() => contentApi.approveSection(script.id, sectionKey, approved), value => {
      const result = value as { section_key: string; approved: boolean };
      const sections = script.sections.map(item => item.section_key === result.section_key ? { ...item, approved: result.approved } : item);
      const next = { ...script, sections };
      setScript(next); setScripts(items => items.map(item => item.id === next.id ? next : item));
    }, approved ? "Script section approved as a narration source." : "Approval removed. Linked narration segments were invalidated.");
  }

  async function regenerateSection(sectionKey: string) {
    if (!script) return;
    await run(() => contentApi.regenerateSection(script.id, sectionKey), async value => {
      const next = value as ScriptDocument; setScript(next); setScripts(items => items.map(item => item.id === next.id ? next : item));
      setVersions(await contentApi.versions(next.id));
    }, "Section regenerated. Previous script content is in version history.");
  }

  async function chooseStoryboard(id: number) {
    const next = storyboards.find(item => item.id === id);
    if (next) { setStoryboard(next); setDraftScenes({}); }
  }

  async function saveScene(scene: Scene) {
    await run(() => contentApi.saveScene(scene.id, {
      title: scene.title, script_section_key: scene.script_section_key, narration_text: scene.narration_text, description: scene.description,
      duration_seconds: scene.duration_seconds, visual_direction: scene.visual_direction,
      historical_events: scene.historical_events, geographic_references: scene.geographic_references,
      claim_ids: scene.claim_ids, source_ids: scene.source_ids, transition_suggestion: scene.transition_suggestion,
    }), updated => {
      const next = updated as Scene;
      setStoryboard(current => current ? { ...current, scenes: current.scenes.map(row => row.id === next.id ? next : row) } : current);
      setDraftScenes(rows => { const copy = { ...rows }; delete copy[scene.id]; return copy; });
    }, "Scene saved.");
  }

  const isResearchBusy = session?.status === "pending" || session?.status === "running";
  const activeScriptSections = useMemo(() => script?.sections ?? [], [script]);

  if (loading) return <section className="content content-studio"><div role="status" className="content-loading">Loading project content workspace…</div></section>;
  if (!projectId) return <section className="content content-studio">
    <div className="eyebrow"><span className="eyebrow-line" /> CONTENT INTELLIGENCE</div><h1>Choose a project<span className="heading-period">.</span></h1><p className="welcome-subtitle">Research, review evidence, and prepare scripts for a project.</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {projects.length ? <div className="content-project-list">{projects.map(item => <button key={item.id} className="content-project" onClick={() => onSelectProject?.(item)}><strong>{item.name}</strong><span>{item.topic || "No topic yet"}</span><span>Open content workspace →</span></button>)}</div> : <div className="projects-empty"><h2>No project to prepare</h2><p>Create a project and add its topic before starting research.</p><button className="secondary-button" onClick={onBack}>Back to projects</button></div>}
  </section>;

  return <section className="content content-studio">
    <div className="content-title-row"><div><div className="eyebrow"><span className="eyebrow-line" /> CONTENT INTELLIGENCE · {project?.name.toUpperCase()}</div><h1>{project?.topic || project?.name}<span className="heading-period">.</span></h1><p className="welcome-subtitle">Prepare sourced research, claims, a script, storyboard, and narration.</p></div><button className="secondary-button" onClick={onBack}>← Project details</button></div>
    {(error || success) && <div className={error ? "inline-error" : "content-success"} role={error ? "alert" : "status"}><span>{error || success}</span>{error && <button className="secondary-button" onClick={() => setError("")}>Dismiss</button>}</div>}
    <nav className="content-tabs" aria-label="Content workflow">{tabs.map(item => <button key={item} className={tab === item ? "selected" : ""} onClick={() => setTab(item)}>{item}{item === "Research" && isResearchBusy && <i className="tab-pending" />}</button>)}</nav>
    {tab === "Research" && <div className="content-panel">
      <div className="provider-strip"><div><span className={`provider-dot ${providers.search_available ? "available" : ""}`} /><span>Search · {providers.search_provider}</span><small>{providers.search_available ? "Ready" : "Credential needed"}</small></div><div><span className={`provider-dot ${providers.ai_available ? "available" : ""}`} /><span>AI · {providers.ai_provider}</span><small>{providers.ai_available ? "Ready" : "Credential needed"}</small></div></div>
      {(!providers.search_available || !providers.ai_available) && <p className="content-note">Provider credentials are read from {providers.credentials_store}. In PowerShell, run <code>services\backend\.venv\Scripts\keyring.exe set GeoChronicle tavily</code> and <code>services\backend\.venv\Scripts\keyring.exe set GeoChronicle openai</code>, then refresh this screen. Secrets stay out of this interface.</p>}
      <details className="provider-settings"><summary>Configure search and AI providers</summary><div className="provider-config-grid"><label className="form-field"><span>Search provider</span><select value={searchProvider} onChange={event => setSearchProvider(event.target.value)}><option value="none">Not configured</option><option value="tavily">Tavily Search</option></select></label><label className="form-field"><span>Search endpoint</span><input value={searchEndpoint} onChange={event => setSearchEndpoint(event.target.value)} maxLength={500} /></label><label className="form-field"><span>AI provider</span><select value={aiProvider} onChange={event => setAiProvider(event.target.value)}><option value="none">Not configured</option><option value="openai_compatible">OpenAI compatible</option></select></label><label className="form-field"><span>AI endpoint</span><input value={aiEndpoint} onChange={event => setAiEndpoint(event.target.value)} maxLength={500} /></label><label className="form-field"><span>AI model</span><input value={aiModel} onChange={event => setAiModel(event.target.value)} maxLength={120} /></label><button className="secondary-button" onClick={() => void saveProviderSettings()} disabled={busy}>Save provider settings</button><p>Use HTTPS provider endpoints. HTTP is limited to localhost for development. Credentials never enter this form.</p></div></details>
      <div className="content-section-heading"><div><h2>Research brief</h2><p>Search sources for the current project topic and extract cited claims.</p></div><span className="project-status">{project?.language} · {project?.visual_style.replace(/_/g, " ")}</span></div>
      <div className="research-options"><label className="form-field form-field-wide"><span>Research topic</span><input value={project?.topic ?? ""} readOnly aria-label="Research topic" /></label><label className="form-field"><span>Maximum sources</span><select value={sourceLimit} onChange={event => setSourceLimit(Number(event.target.value))}><option value={4}>4 sources</option><option value={8}>8 sources</option><option value={10}>10 sources</option></select></label><label className="form-field"><span>Region or countries (optional)</span><input value={region} onChange={event => setRegion(event.target.value)} maxLength={120} placeholder="e.g. South Asia" /></label><label className="form-field form-field-wide"><span>Date range (optional)</span><input value={dateRange} onChange={event => setDateRange(event.target.value)} maxLength={120} placeholder="e.g. 1947–1971" /></label></div>
      <div className="content-actions"><button className="primary-button" onClick={() => void startResearch()} disabled={busy || isResearchBusy || !project?.topic}>{busy ? "Working…" : isResearchBusy ? "Research in progress…" : "Start research"}</button><label className="session-picker"><span>Previous sessions</span><select aria-label="Select previous research session" value={session?.id ?? ""} onChange={event => void selectResearch(Number(event.target.value))}><option value="" disabled>Select a saved session</option>{sessions.map(item => <option key={item.id} value={item.id}>{item.topic} · {item.status} · #{item.id}</option>)}</select></label></div>
      {session && <div className="research-results"><div className="session-state"><span className={`state-indicator ${session.status === "completed" ? "ready" : session.status}`} /><div><strong>{session.status === "completed" ? "Research ready for review" : session.status === "failed" ? "Research stopped" : "Research is running"}</strong><small>{session.progress || session.error || `Session ${session.id}`}</small></div>{session.status === "completed" && <span>{sources.length} sources · {claims.length} claims</span>}</div>
        {session.error && <p className="form-error">{session.error}</p>}{session.overview && <div className="research-overview"><h3>Research summary</h3><p>{session.overview}</p>{session.perspectives.length > 0 && <p><strong>Perspectives to compare: </strong>{session.perspectives.join(" · ")}</p>}</div>}
        {session.status === "completed" && <div className="source-claim-grid"><div><h3>Sources</h3>{sources.length ? <ul className="source-list">{sources.map(item => <li key={item.id}><button onClick={() => void run(() => contentApi.source(item.id), setSelectedSource)}><strong>{item.title}</strong><small>{item.publisher || new URL(item.url).hostname}</small></button></li>)}</ul> : <p className="muted-text">No source records were returned.</p>}</div><div><h3>Extracted claims</h3><p className="muted-text">Claims begin unverified and remain so until reviewed.</p>{claims.slice(0, 8).map(item => <div className="mini-claim" key={item.id}><span>{verificationLabels[item.verification_status] || item.verification_status}</span><p>{item.text}</p></div>)}<button className="text-button" onClick={() => setTab("Fact-check")}>Review all claims →</button></div></div>}
      </div>}
      {selectedSource && <section className="source-detail"><div className="content-section-heading"><h3>{selectedSource.title}</h3><button className="text-button" onClick={() => setSelectedSource(null)}>Close</button></div><p>{selectedSource.summary || selectedSource.content || "No extracted source excerpt is available."}</p><dl><div><dt>Publisher</dt><dd>{selectedSource.publisher || "Unknown"}</dd></div><div><dt>Published</dt><dd>{selectedSource.publication_date || "Not provided"}</dd></div><div><dt>Retrieved</dt><dd>{new Date(selectedSource.retrieved_at).toLocaleString()}</dd></div><div><dt>Type</dt><dd>{selectedSource.source_type}</dd></div></dl><a href={selectedSource.url} target="_blank" rel="noreferrer">Open original source ↗</a>{selectedSource.reliability_assessment && <p>{selectedSource.reliability_assessment}</p>}</section>}
    </div>}
    {tab === "Fact-check" && <div className="content-panel"><div className="content-section-heading"><div><h2>Claim review</h2><p>Evidence links are preserved with each claim. AI assessments are suggestions and require your review.</p></div>{session && <span className="project-status">{claims.length} claims</span>}</div>{!session || claims.length === 0 ? <div className="content-empty"><h3>No claims to review</h3><p>Complete research for this project to extract claims with source references.</p><button className="secondary-button" onClick={() => setTab("Research")}>Go to research</button></div> : <div className="claim-list">{claims.map(item => <ClaimCard key={item.id} claim={item} notes={claimNotes[item.id] ?? item.reviewer_notes ?? ""} busy={busy} checks={claimChecks[item.id] ?? []} onNotes={value => setClaimNotes(current => ({ ...current, [item.id]: value }))} onCheck={() => void run(() => contentApi.factCheck(item.id), result => { setClaimChecks(items => ({ ...items, [item.id]: [result as FactCheck, ...(items[item.id] ?? [])] })); }, "AI fact-check suggestion saved. Review the evidence before updating status.")} onSave={status => void run(() => contentApi.reviewClaim(item.id, status, claimNotes[item.id] ?? item.reviewer_notes), value => setClaims(rows => rows.map(row => row.id === item.id ? value as Claim : row)), "Claim review saved.")} />)}</div>}</div>}
    {tab === "Script" && <div className="content-panel"><div className="content-section-heading"><div><h2>Script editor</h2><p>Save or regenerate versions, then approve sections before using them as narration sources.</p></div><div className="content-actions"><label className="session-picker"><span>Saved scripts</span><select value={script?.id ?? ""} onChange={event => { const saved = scripts.find(item => item.id === Number(event.target.value)); if (saved) void openScript(saved); }}><option value="" disabled>Select script</option>{scripts.map(item => <option key={item.id} value={item.id}>{item.title} · #{item.id}</option>)}</select></label><button className="primary-button" onClick={() => project && void run(() => contentApi.generateScript(project.id, session?.id ?? null), async value => { const saved = value as ScriptDocument; setScript(saved); setScripts(items => [saved, ...items]); setVersions(await contentApi.versions(saved.id)); }, "Script generated and saved.")} disabled={busy || !providers.ai_available}>{busy ? "Generating…" : "Generate script"}</button></div></div>{script ? <><div className="version-strip"><strong>{script.title}</strong><span>{versions.length} saved versions</span><button className="text-button" onClick={() => setSuccess(versions.map(v => `v${v.version_number}: ${v.change_note}`).join(" · ") || "No versions saved yet.")}>Version history</button></div><div className="script-sections">{activeScriptSections.map(section => <article className="script-section" key={section.id}><div className="script-section-heading"><div><span>SECTION {String(section.position + 1).padStart(2, "0")}</span><h3>{section.title}</h3><small className={`approval-state${section.approved ? " approved" : ""}`}>{section.approved ? "Approved narration source" : "Not approved for narration"}</small></div><div><button className="secondary-button" disabled={busy || !providers.ai_available} onClick={() => void regenerateSection(section.section_key)}>Regenerate section</button><button className="secondary-button" disabled={busy} onClick={() => void saveSection(section.section_key)}>Save section</button><button className={section.approved ? "secondary-button approval-button approved" : "secondary-button approval-button"} disabled={busy} onClick={() => void setSectionApproval(section.section_key, !section.approved)}>{section.approved ? "Revoke approval" : "Approve for narration"}</button></div></div><textarea aria-label={`${section.title} script text`} value={draftSections[section.section_key] ?? section.content} onChange={event => setDraftSections(current => ({ ...current, [section.section_key]: event.target.value }))} maxLength={12000} rows={Math.max(5, Math.min(14, Math.ceil((section.content.length || 1) / 90)))} /></article>)}</div></> : <div className="content-empty"><h3>No script saved</h3><p>Generate a script from the latest research. The selected project language and duration are included.</p></div>}</div>}
    {tab === "Storyboard" && <div className="content-panel"><div className="content-section-heading"><div><h2>Storyboard</h2><p>Scene schema version 1.1. Each scene points back to its script section and research references.</p></div><div className="content-actions"><label className="session-picker"><span>Saved boards</span><select value={storyboard?.id ?? ""} onChange={event => void chooseStoryboard(Number(event.target.value))}><option value="" disabled>Select storyboard</option>{storyboards.map(item => <option key={item.id} value={item.id}>Storyboard #{item.id} · {item.scenes.length} scenes</option>)}</select></label><button className="primary-button" onClick={() => script && void run(() => contentApi.generateStoryboard(script.id), board => { const saved = board as Storyboard; setStoryboard(saved); setStoryboards(items => [saved, ...items]); setDraftScenes({}); }, "Storyboard generated and saved.")} disabled={busy || !script || !providers.ai_available}>{busy ? "Generating…" : "Generate storyboard"}</button></div></div>{storyboard ? <div className="scene-list">{storyboard.scenes.map(scene => <SceneEditor key={scene.id} scene={draftScenes[scene.id] ?? scene} sections={script?.sections ?? []} busy={busy} onChange={next => setDraftScenes(rows => ({ ...rows, [scene.id]: next }))} onSave={() => void saveScene(draftScenes[scene.id] ?? scene)} />)}</div> : <div className="content-empty"><h3>No storyboard yet</h3><p>Generate one from a saved script.</p><button className="secondary-button" onClick={() => setTab("Script")}>Open script editor</button></div>}</div>}
    {tab === "Narration" && <div className="content-panel"><div className="content-section-heading"><div><h2>Narration preparation</h2><p>Sentence segments inherit scene associations. Duration is an estimate based on the selected speech rate.</p></div><div className="content-actions"><label className="form-field rate-field"><span>Words per minute</span><input type="number" min={80} max={250} value={speechRate} onChange={event => setSpeechRate(Number(event.target.value))} /></label><button className="primary-button" onClick={() => storyboard && void run(() => contentApi.prepareNarration(storyboard.id, speechRate), result => setNarration((result as { segments: NarrationSegment[] }).segments), "Narration segments prepared.")} disabled={busy || !storyboard}>{busy ? "Preparing…" : "Prepare narration"}</button></div></div>{narration.length ? <div className="narration-list">{narration.map((item, index) => <article className="narration-item" key={`${item.scene_id}-${item.segment_number}`}><div><span>SCENE {item.scene_number ?? storyboard?.scenes.find(scene => scene.id === item.scene_id)?.scene_number} · SENTENCE {item.segment_number}</span><strong>{item.estimated_duration_seconds.toFixed(1)} sec</strong></div><textarea aria-label={`Narration segment ${index + 1}`} value={draftNarration[item.id ?? index] ?? item.text} onChange={event => setDraftNarration(current => ({ ...current, [item.id ?? index]: event.target.value }))} rows={3} /><button className="secondary-button" disabled={busy || item.id === undefined} onClick={() => { if (item.id === undefined) return; const segmentId = item.id; void run(() => contentApi.saveNarration(segmentId, draftNarration[segmentId] ?? item.text, speechRate), updated => setNarration(rows => rows.map(row => row.id === (updated as NarrationSegment).id ? updated as NarrationSegment : row)), "Narration segment saved."); }}>Save segment</button></article>)}</div> : <div className="content-empty"><h3>No narration segments</h3><p>Prepare narration after generating a storyboard. Sentence boundaries and punctuation are preserved.</p></div>}</div>}
  </section>;
}

function ClaimCard({ claim, notes, busy, checks, onNotes, onCheck, onSave }: { claim: Claim; notes: string; busy: boolean; checks: FactCheck[]; onNotes: (value: string) => void; onCheck: () => void; onSave: (status: string) => void }) {
  const [status, setStatus] = useState(claim.verification_status);
  return <article className="claim-card"><div className="claim-top"><span className={`claim-category category-${claim.category}`}>{claim.category}</span><span className={`claim-status status-${claim.verification_status}`}>{verificationLabels[claim.verification_status] || claim.verification_status}</span></div><p className="claim-text">{claim.text}</p><div className="claim-evidence"><h4>Source evidence ({claim.sources.length})</h4>{claim.sources.length ? claim.sources.map(source => <div className="evidence-row" key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a><small>{source.relationship_type} · {source.publisher || new URL(source.url).hostname}</small>{source.evidence && <p>{source.evidence}</p>}</div>) : <p className="muted-text">Unsupported claim: no source is associated with this claim.</p>}</div>{checks.map(check => <div className="fact-check-suggestion" key={check.id}><strong>AI suggestion · {verificationLabels[check.suggested_status] || check.suggested_status}</strong><span>{check.confidence === null ? "No confidence supplied" : `Model confidence ${Math.round(check.confidence * 100)}%`} · reviewer action required</span><p>{check.supporting_evidence.length} supporting excerpts · {check.contradicting_evidence.length} contradicting excerpts</p></div>)}<div className="claim-review"><label className="form-field"><span>Reviewer status</span><select value={status} onChange={event => setStatus(event.target.value)}>{Object.entries(verificationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label className="form-field"><span>Reviewer notes</span><textarea value={notes} maxLength={4000} rows={2} onChange={event => onNotes(event.target.value)} placeholder="Record evidence or explain your review" /></label><div><button className="secondary-button" onClick={onCheck} disabled={busy}>Run fact-check suggestion</button><button className="primary-button" onClick={() => onSave(status)} disabled={busy}>Save review</button></div></div></article>;
}

function SceneEditor({ scene, sections, busy, onChange, onSave }: { scene: Scene; sections: ScriptDocument["sections"]; busy: boolean; onChange: (scene: Scene) => void; onSave: () => void }) {
  const update = (changes: Partial<Scene>) => onChange({ ...scene, ...changes });
  return <article className="scene-card"><div className="scene-heading"><span>SCENE {String(scene.scene_number).padStart(2, "0")}</span><strong>{scene.duration_seconds}s</strong></div><label className="form-field"><span>Scene title</span><input value={scene.title} maxLength={200} onChange={event => update({ title: event.target.value })} /></label><label className="form-field"><span>Script source section</span><select value={scene.script_section_key ?? ""} onChange={event => update({ script_section_key: event.target.value || null })}><option value="">No script section</option>{sections.map(section => <option key={section.section_key} value={section.section_key}>{section.title}{section.approved ? " · approved" : ""}</option>)}</select></label><div className="scene-grid"><label className="form-field"><span>Duration seconds</span><input type="number" min={1} max={600} value={scene.duration_seconds} onChange={event => update({ duration_seconds: Number(event.target.value) })} /></label><label className="form-field"><span>Geographic references</span><input value={scene.geographic_references.join(", ")} onChange={event => update({ geographic_references: event.target.value.split(",").map(value => value.trim()).filter(Boolean) })} placeholder="Cities, regions, countries" /></label></div><label className="form-field"><span>Narration</span><textarea rows={4} value={scene.narration_text} maxLength={12000} onChange={event => update({ narration_text: event.target.value })} /></label><label className="form-field"><span>Scene description</span><textarea rows={2} value={scene.description} maxLength={8000} onChange={event => update({ description: event.target.value })} /></label><label className="form-field"><span>Visual direction</span><textarea rows={3} value={scene.visual_direction} maxLength={8000} onChange={event => update({ visual_direction: event.target.value })} /></label><div className="scene-footer"><span>{scene.historical_events.join(" · ") || "No event references"} · {scene.source_ids.length} source refs · {scene.claim_ids.length} claim refs</span><button className="primary-button" onClick={onSave} disabled={busy}>Save scene</button></div></article>;
}
