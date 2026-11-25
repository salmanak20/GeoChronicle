import { invoke } from "@tauri-apps/api/core";
import type { Claim, FactCheck, NarrationSegment, ProviderStatus, ResearchSession, ResearchSource, Scene, ScriptDocument, Storyboard } from "../../types/content";

export const contentApi = {
  providers: () => invoke<ProviderStatus>("provider_status"),
  saveProviderConfiguration: (configuration: { searchProvider?: string; searchEndpoint?: string; aiProvider?: string; aiEndpoint?: string; aiModel?: string }) => invoke<ProviderStatus>("save_provider_configuration", configuration),
  startResearch: (projectId: number, topic: string, sourceLimit: number, region: string, dateRange: string) => invoke<ResearchSession>("start_research", { projectId, topic: topic || null, sourceLimit, includePrimarySources: true, region: region || null, dateRange: dateRange || null }),
  researchSessions: (projectId: number) => invoke<ResearchSession[]>("project_research_sessions", { projectId }),
  researchStatus: (sessionId: number) => invoke<ResearchSession>("research_status", { sessionId }),
  sources: (sessionId: number) => invoke<ResearchSource[]>("research_sources", { sessionId, page: 1, pageSize: 100 }),
  source: (sourceId: number) => invoke<ResearchSource>("source_detail", { sourceId }),
  claims: (sessionId: number) => invoke<Claim[]>("research_claims", { sessionId }),
  reviewClaim: (claimId: number, verificationStatus: string | null, reviewerNotes: string | null) => invoke<Claim>("review_claim", { claimId, verificationStatus, reviewerNotes }),
  factCheck: (claimId: number) => invoke<FactCheck>("fact_check_claim", { claimId }),
  factCheckResults: (claimId: number) => invoke<FactCheck[]>("fact_check_results", { claimId }),
  generateScript: (projectId: number, researchSessionId: number | null) => invoke<ScriptDocument>("generate_script", { projectId, researchSessionId, audience: "general audience", narrativeStructure: "documentary" }),
  scripts: (projectId: number) => invoke<ScriptDocument[]>("project_scripts", { projectId }),
  script: (scriptId: number) => invoke<ScriptDocument>("get_script", { scriptId }),
  saveSection: (scriptId: number, sectionKey: string, content: string) => invoke<ScriptDocument>("update_script_section", { scriptId, sectionKey, content, changeNote: "Edited script section" }),
  approveSection: (scriptId: number, sectionKey: string, approved: boolean) => invoke<{ script_id: number; section_key: string; approved: boolean }>("set_script_section_approval", { scriptId, sectionKey, approved }),
  regenerateSection: (scriptId: number, sectionKey: string) => invoke<ScriptDocument>("regenerate_script_section", { scriptId, sectionKey }),
  versions: (scriptId: number) => invoke<Array<{ id: number; version_number: number; sections: Array<{ section_key: string; title: string; content: string }>; change_note: string; created_at: string }>>("script_versions", { scriptId }),
  generateStoryboard: (scriptId: number) => invoke<Storyboard>("generate_storyboard", { scriptId }),
  storyboards: (scriptId: number) => invoke<Storyboard[]>("script_storyboards", { scriptId }),
  saveScene: (sceneId: number, scene: Omit<Scene, "id" | "scene_number">) => invoke<Scene>("update_storyboard_scene", { sceneId, payload: scene }),
  prepareNarration: (storyboardId: number, wordsPerMinute: number) => invoke<{ storyboard_id: number; words_per_minute: number; segments: NarrationSegment[] }>("prepare_narration", { storyboardId, wordsPerMinute }),
  narration: (storyboardId: number) => invoke<NarrationSegment[]>("storyboard_narration", { storyboardId }),
  saveNarration: (segmentId: number, text: string, wordsPerMinute: number) => invoke<NarrationSegment>("update_narration_segment", { segmentId, text, wordsPerMinute }),
};

export function errorMessage(reason: unknown): string { return typeof reason === "string" ? reason : "The content workspace request failed. Please retry."; }
