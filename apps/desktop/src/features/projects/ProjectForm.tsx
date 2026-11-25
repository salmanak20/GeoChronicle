import { useState, type FormEvent } from "react";
import type { Project, ProjectInput, ProjectStatus } from "../../types/project";
import { projectStatusLabels } from "../../types/project";

interface ProjectFormProps {
  initial?: Project;
  busy?: boolean;
  onCancel: () => void;
  onSubmit: (values: ProjectInput & { status?: ProjectStatus }) => Promise<void>;
}

export function ProjectForm({ initial, busy = false, onCancel, onSubmit }: ProjectFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [topic, setTopic] = useState(initial?.topic ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [duration, setDuration] = useState(initial?.target_duration_seconds?.toString() ?? "");
  const [aspectRatio, setAspectRatio] = useState(initial?.aspect_ratio ?? "16:9");
  const [language, setLanguage] = useState(initial?.language ?? "en");
  const [visualStyle, setVisualStyle] = useState(initial?.visual_style ?? "hybrid");
  const [status, setStatus] = useState<ProjectStatus>(initial?.status ?? "draft");
  const [validationError, setValidationError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setValidationError("Enter a project name to continue.");
      return;
    }
    const seconds = duration.trim() ? Number(duration) : null;
    if (seconds !== null && (!Number.isInteger(seconds) || seconds < 30 || seconds > 7200)) {
      setValidationError("Duration must be between 30 seconds and 2 hours.");
      return;
    }
    if (!/^[a-z]{2}(-[A-Z]{2})?$/.test(language.trim())) {
      setValidationError("Use a language code such as en or en-US.");
      return;
    }
    setValidationError("");
    await onSubmit({
      name: name.trim(),
      topic: topic.trim() || null,
      description: description.trim() || null,
      target_duration_seconds: seconds,
      aspect_ratio: aspectRatio,
      language: language.trim(),
      visual_style: visualStyle,
      ...(initial ? { status } : {}),
    });
  }

  return <form className="project-form" onSubmit={submit} noValidate>
    <div className="form-intro">
      <span className="eyebrow"><span className="eyebrow-line" /> PROJECT BRIEF</span>
      <h2>{initial ? "Edit project" : "Create a project"}</h2>
      <p>Set the foundation for your documentary. You can refine these details later.</p>
    </div>
    <label className="form-field form-field-wide">Project name <span aria-hidden="true">*</span>
      <input autoFocus maxLength={200} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. The Silk Road: A World Connected" aria-required="true" />
    </label>
    <label className="form-field form-field-wide">Topic
      <input maxLength={500} value={topic} onChange={event => setTopic(event.target.value)} placeholder="The people, place or turning point at the heart of the story" />
    </label>
    <label className="form-field form-field-wide">Description
      <textarea maxLength={5000} rows={4} value={description} onChange={event => setDescription(event.target.value)} placeholder="Add context or notes for this project" />
    </label>
    <div className="form-field-grid">
      <label className="form-field">Target duration
        <div className="input-suffix"><input type="number" min={30} max={7200} step={1} value={duration} onChange={event => setDuration(event.target.value)} placeholder="Optional" /><span>sec</span></div>
      </label>
      <label className="form-field">Aspect ratio
        <select value={aspectRatio} onChange={event => setAspectRatio(event.target.value)}><option value="16:9">16:9 · Landscape</option><option value="9:16">9:16 · Portrait</option><option value="1:1">1:1 · Square</option><option value="4:3">4:3 · Classic</option></select>
      </label>
      <label className="form-field">Language
        <input maxLength={12} value={language} onChange={event => setLanguage(event.target.value)} placeholder="en" />
      </label>
      <label className="form-field">Visual direction
        <select value={visualStyle} onChange={event => setVisualStyle(event.target.value)}><option value="hybrid">Hybrid · maps + scenes</option><option value="cinematic">Cinematic scenes</option><option value="animated_maps">Animated maps</option></select>
      </label>
      {initial && <label className="form-field">Project status
        <select value={status} onChange={event => setStatus(event.target.value as ProjectStatus)}>{Object.entries(projectStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      </label>}
    </div>
    {validationError && <p className="form-error" role="alert">{validationError}</p>}
    <div className="form-actions"><button type="button" className="secondary-button" onClick={onCancel} disabled={busy}>Cancel</button><button type="submit" className="primary-button" disabled={busy}>{busy ? "Saving…" : initial ? "Save changes" : "Create project"}</button></div>
  </form>;
}
