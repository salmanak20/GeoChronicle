export type ResearchSession = {
  id: number; project_id: number; topic: string; configuration: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed"; progress: string | null; error: string | null;
  overview: string | null; perspectives: string[]; created_at: string; completed_at: string | null;
};
export type ResearchSource = {
  id: number; title: string; url: string; publisher: string | null; author: string | null;
  publication_date: string | null; retrieved_at: string; source_type: string; content: string | null;
  summary: string | null; reliability_assessment: string | null; provenance: Record<string, unknown>;
};
export type ClaimSource = { id: number; title: string; url: string; publisher: string | null; relationship_type: string; evidence: string | null };
export type Claim = { id: number; session_id: number; text: string; category: "fact" | "interpretation" | "estimate" | "opinion"; verification_status: string; confidence: number | null; reviewer_notes: string | null; sources: ClaimSource[] };
export type ScriptSection = { id: number; section_key: string; title: string; content: string; approved: boolean; position: number };
export type ScriptDocument = { id: number; project_id: number; research_session_id: number | null; title: string; updated_at: string; sections: ScriptSection[] };
export type Scene = { id: number; scene_number: number; title: string; script_section_key: string | null; narration_text: string; description: string; duration_seconds: number; visual_direction: string; historical_events: string[]; geographic_references: string[]; claim_ids: number[]; source_ids: number[]; transition_suggestion: string | null };
export type Storyboard = { id: number; script_id: number; schema_version: string; scenes: Scene[] };
export type NarrationSegment = { id?: number; scene_id: number; scene_number?: number; segment_number: number; paragraph_number?: number; text: string; estimated_duration_seconds: number };
export type ProviderStatus = { search_provider: string; search_endpoint: string; search_available: boolean; ai_provider: string; ai_endpoint: string; ai_model: string; ai_available: boolean; credentials_store: string };
export type FactCheck = { id: number; suggested_status: string; confidence: number | null; supporting_evidence: string[]; contradicting_evidence: string[]; method: string; created_at: string; review_required: boolean };
