import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Project } from "../../types/project";
import { ContentWorkspace } from "./ContentWorkspace";

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
vi.mock("../projects/projectApi", () => ({ projectApi: { get: vi.fn(), list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), stats: vi.fn() } }));

const project: Project = { id: 4, name: "Archive story", topic: "Test topic", description: null, status: "draft", target_duration_seconds: 300, aspect_ratio: "16:9", language: "en", visual_style: "cinematic", created_at: "2026-11-25T10:00:00Z", updated_at: "2026-11-25T10:00:00Z" };
const session = { id: 10, project_id: 4, topic: "Test topic", configuration: {}, status: "completed" as const, progress: "Research ready for review", error: null, overview: "Two sourced perspectives are available.", perspectives: ["archival", "contemporary"], created_at: "2026-11-25T10:00:00Z", completed_at: "2026-11-25T10:01:00Z" };
const source = { id: 21, title: "National archive", url: "https://archive.example/item", publisher: "National archive", author: null, publication_date: null, retrieved_at: "2026-11-25T10:00:00Z", source_type: "other", content: "A dated primary record.", summary: "A dated primary record.", reliability_assessment: null, provenance: { provider: "mock" } };
const claim = { id: 30, session_id: 10, text: "A sourced historical claim.", category: "fact" as const, verification_status: "unverified", confidence: null, reviewer_notes: null, sources: [{ id: 21, title: source.title, url: source.url, publisher: source.publisher, relationship_type: "supporting", evidence: "A dated primary record." }] };
const section = { id: 40, section_key: "hook", title: "Hook", content: "Initial opening.", approved: true, position: 0 };
const script = { id: 50, project_id: 4, research_session_id: 10, title: "Archive story script", updated_at: "2026-11-25T10:00:00Z", sections: [section] };
const scene = { id: 60, scene_number: 1, title: "A document", script_section_key: "hook", narration_text: "A record surfaced. It changed the story!", description: "Show the document.", duration_seconds: 18, visual_direction: "Archival close-up.", historical_events: ["Record discovered"], geographic_references: ["Europe"], claim_ids: [30], source_ids: [21], transition_suggestion: "Fade through ink" };
const board = { id: 70, script_id: 50, schema_version: "1.0", scenes: [scene] };

function setupInvoke() {
  invoke.mockImplementation(async (command: string) => {
    switch (command) {
      case "get_project": return project;
      case "provider_status": return { search_provider: "tavily", search_endpoint: "https://search.example/api", search_available: true, ai_provider: "openai_compatible", ai_endpoint: "https://model.example/v1/chat/completions", ai_model: "test-model", ai_available: true, credentials_store: "Windows Credential Manager" };
      case "project_research_sessions": return [session];
      case "project_scripts": return [script];
      case "research_status": return session;
      case "research_sources": return [source];
      case "research_claims": return [claim];
      case "source_detail": return source;
      case "script_versions": return [{ id: 1, version_number: 1, sections: [section], change_note: "Generated script", created_at: "2026-11-25T10:00:00Z" }];
      case "script_storyboards": return [board];
      case "get_script": return script;
      case "storyboard_narration": return [];
      case "fact_check_claim": return { id: 9, suggested_status: "supported", confidence: 0.8, supporting_evidence: ["One excerpt"], contradicting_evidence: [], method: "ai_assisted_suggestion", created_at: "2026-11-25T10:00:00Z", review_required: true };
      case "review_claim": return { ...claim, verification_status: "supported", reviewer_notes: "Reviewed" };
      case "update_script_section": return { ...script, sections: [{ ...section, content: "Edited opening." }] };
      case "set_script_section_approval": return { script_id: 50, section_key: "hook", approved: true };
      case "save_provider_configuration": return { search_provider: "tavily", search_endpoint: "https://search.example/api", search_available: true, ai_provider: "openai_compatible", ai_endpoint: "https://model.example/v1/chat/completions", ai_model: "test-model", ai_available: true, credentials_store: "Windows Credential Manager" };
      case "generate_script": return script;
      case "generate_storyboard": return board;
      case "update_storyboard_scene": return scene;
      case "prepare_narration": return { storyboard_id: 70, words_per_minute: 145, segments: [{ id: 80, scene_id: 60, scene_number: 1, segment_number: 1, paragraph_number: 1, text: "A record surfaced.", estimated_duration_seconds: 0.8 }] };
      case "update_narration_segment": return { id: 80, scene_id: 60, segment_number: 1, paragraph_number: 1, text: "Edited sentence.", estimated_duration_seconds: 0.8 };
      default: throw new Error(`Unexpected command ${command}`);
    }
  });
}

beforeEach(() => { vi.clearAllMocks(); setupInvoke(); });

describe("ContentWorkspace", () => {
  it("shows sourced research and opens source detail and claim review", async () => {
    const user = userEvent.setup();
    render(<ContentWorkspace projectId={project.id} onBack={vi.fn()} />);
    await screen.findByText("Two sourced perspectives are available.");
    expect((await screen.findAllByText("National archive")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /National archive/ }));
    expect(await screen.findByText("A dated primary record.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fact-check" }));
    expect(await screen.findByText("A sourced historical claim.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run fact-check suggestion" }));
    expect(await screen.findByText(/AI suggestion · Supported/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Reviewer status"), "supported");
    await user.click(screen.getByRole("button", { name: "Save review" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("review_claim", expect.objectContaining({ claimId: 30, verificationStatus: "supported" })));
  });

  it("edits and saves script sections with version history", async () => {
    const user = userEvent.setup();
    render(<ContentWorkspace projectId={project.id} onBack={vi.fn()} />);
    await screen.findByText("Two sourced perspectives are available.");
    await user.click(screen.getByRole("button", { name: "Script" }));
    const editor = await screen.findByRole("textbox", { name: "Hook script text" });
    await user.clear(editor);
    await user.type(editor, "Edited opening.");
    await user.click(screen.getByRole("button", { name: "Save section" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("update_script_section", expect.objectContaining({ scriptId: 50, sectionKey: "hook", content: "Edited opening." })));
  });

  it("saves storyboard scenes and narration segments", async () => {
    const user = userEvent.setup();
    render(<ContentWorkspace projectId={project.id} onBack={vi.fn()} />);
    await screen.findByText("Two sourced perspectives are available.");
    await user.click(screen.getByRole("button", { name: "Storyboard" }));
    await user.clear(screen.getByLabelText("Scene title"));
    await user.type(screen.getByLabelText("Scene title"), "Edited scene");
    await user.click(screen.getByRole("button", { name: "Save scene" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("update_storyboard_scene", expect.objectContaining({ sceneId: 60, payload: expect.objectContaining({ script_section_key: "hook" }) })));
    await user.click(screen.getByRole("button", { name: "Narration" }));
    await user.click(screen.getByRole("button", { name: "Prepare narration" }));
    const editor = await screen.findByRole("textbox", { name: "Narration segment 1" });
    await user.clear(editor);
    await user.type(editor, "Edited sentence.");
    await user.click(screen.getByRole("button", { name: "Save segment" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("update_narration_segment", expect.objectContaining({ segmentId: 80, text: "Edited sentence." })));
  });
});
