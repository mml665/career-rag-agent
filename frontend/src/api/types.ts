// ---- CandidateProfile ----
export interface CandidateProfile {
  name: string
  phone: string
  email: string
  city: string
  target_role: string
  preferred_locations: string
  homepage: string
  summary: string
  updated_at: string
}

// ---- ProfileEvidence ----
export interface ProfileEvidence {
  evidence_id: string
  category: string
  content: string
  title: string
  source_file: string
  source_page: number | null
  verified: boolean
  created_at: string
}

// ---- JobPosting ----
export interface JobPosting {
  job_id: string
  company: string
  title: string
  location: string
  raw_description: string
  source_url: string
  required_skills: string[]
  preferred_skills: string[]
  internship_requirements: string[]
  created_at: string
}

// ---- MatchAnalysis ----
export interface MatchAnalysis {
  analysis_id: string
  job_id: string
  score: number
  matched_requirements: string[]
  missing_requirements: string[]
  matched_preferred_skills: string[]
  missing_preferred_skills: string[]
  evidence_ids: string[]
  evidence_map: Record<string, string[]>
  resume_suggestions: string[]
  created_at: string
  analysis_type: string
  keyword_score: number | null
  semantic_score: number | null
  semantic_evidence_ids: string[]
  model_explanation: string
  is_stale: boolean
  invalidated_at: string
}

// ---- ResumeVersion ----
export interface ResumeVersion {
  version_id: string
  job_id: string
  name: string
  content: string
  target_category: string
  fit_assessment: string
  evidence_basis: string
  gap_notes: string
  created_at: string
}

// ---- ApplicationRecord ----
export interface ApplicationRecord {
  application_id: string
  job_id: string
  status: string
  analysis_id: string
  resume_version: string
  resume_version_id: string
  submitted_at: string
  notes: string
  created_at: string
  updated_at: string
}

// ---- Library / RAG ----
export interface AskResponse {
  question: string
  answer: string
  sources: SearchResult[]
}

export interface SearchResult {
  source: string
  chunk_index: number
  content: string
  score: number
  accepted: boolean
}

export interface DocumentInfo {
  name: string
  path: string
  size: number
}

export interface HistoryRecord {
  history_id: string
  question: string
  answer: string
  sources: any[]
  created_at: string
}

// ---- Agent ----
export interface AgentStepResponse {
  tool_name: string
  tool_input: Record<string, any>
  tool_output: string
}

export interface AgentResponse {
  answer: string
  steps: AgentStepResponse[]
  success: boolean
  error: string
}

// ---- Extraction Results ----
export interface ResumeExtraction {
  name: string
  phone: string
  email: string
  city: string
  target_role: string
  preferred_locations: string
  homepage: string
  summary: string
  education: string
  skill: string
  project: string
  award: string
  availability: string
}

export interface JobExtraction {
  company: string
  title: string
  location: string
  required_skills: string[]
  preferred_skills: string[]
  internship_requirements: string[]
}

export interface TailorResult {
  fit_assessment: string
  recommended_text: string
  evidence_basis: string
  gap_notes: string
}

// ---- Semantic Match ----
export interface SemanticMatchResult {
  semantic_score: number
  semantic_evidence_ids: string[]
  model_explanation: string
}
