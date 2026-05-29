from pydantic import BaseModel


# ---- CandidateProfile ----

class CandidateProfileResponse(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    target_role: str = ""
    preferred_locations: str = ""
    homepage: str = ""
    summary: str = ""
    updated_at: str = ""


class CandidateProfileCreate(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    target_role: str = ""
    preferred_locations: str = ""
    homepage: str = ""
    summary: str = ""


# ---- ProfileEvidence ----

class ProfileEvidenceResponse(BaseModel):
    evidence_id: str
    category: str
    content: str
    title: str = ""
    source_file: str = ""
    source_page: int | None = None
    verified: bool = True
    created_at: str = ""


class ProfileEvidenceCreate(BaseModel):
    category: str
    content: str
    title: str = ""
    source_file: str = ""
    source_page: int | None = None
    verified: bool = True


class ProfileEvidenceUpdate(BaseModel):
    category: str
    content: str
    source_file: str = ""
    source_page: int | None = None
    verified: bool = True


class ProfileSectionsRequest(BaseModel):
    sections: dict[str, str]
    source_file: str = ""
    verified: bool = True


# ---- JobPosting ----

class JobPostingResponse(BaseModel):
    job_id: str
    company: str
    title: str
    location: str
    raw_description: str
    source_url: str = ""
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    internship_requirements: list[str] = []
    created_at: str = ""


class JobPostingCreate(BaseModel):
    company: str
    title: str
    location: str = ""
    raw_description: str
    source_url: str = ""
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    internship_requirements: list[str] = []


# ---- MatchAnalysis ----

class MatchAnalysisResponse(BaseModel):
    analysis_id: str
    job_id: str
    score: float
    matched_requirements: list[str] = []
    missing_requirements: list[str] = []
    matched_preferred_skills: list[str] = []
    missing_preferred_skills: list[str] = []
    evidence_ids: list[str] = []
    evidence_map: dict[str, list[str]] = {}
    resume_suggestions: list[str] = []
    created_at: str = ""
    analysis_type: str = "keyword"
    keyword_score: float | None = None
    semantic_score: float | None = None
    semantic_evidence_ids: list[str] = []
    model_explanation: str = ""
    is_stale: bool = False
    invalidated_at: str = ""


class MatchAnalysisEnhance(BaseModel):
    semantic_score: float
    semantic_evidence_ids: list[str] = []
    model_explanation: str = ""


# ---- ResumeVersion ----

class ResumeVersionResponse(BaseModel):
    version_id: str
    job_id: str
    name: str
    content: str
    target_category: str = "project"
    fit_assessment: str = ""
    evidence_basis: str = ""
    gap_notes: str = ""
    created_at: str = ""


class ResumeVersionCreate(BaseModel):
    job_id: str
    name: str
    content: str
    target_category: str = "project"
    fit_assessment: str = ""
    evidence_basis: str = ""
    gap_notes: str = ""


# ---- ApplicationRecord ----

class ApplicationRecordResponse(BaseModel):
    application_id: str
    job_id: str
    status: str = "planned"
    analysis_id: str = ""
    resume_version: str = ""
    resume_version_id: str = ""
    submitted_at: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


class ApplicationRecordCreate(BaseModel):
    job_id: str
    status: str = "planned"
    analysis_id: str = ""
    resume_version: str = ""
    resume_version_id: str = ""
    submitted_at: str = ""
    notes: str = ""


class ApplicationRecordUpdate(BaseModel):
    status: str
    resume_version: str = ""
    resume_version_id: str = ""
    submitted_at: str = ""
    notes: str = ""


# ---- Library (RAG) ----

class AskRequest(BaseModel):
    question: str
    top_k: int = 4


class SearchRequest(BaseModel):
    question: str
    top_k: int = 5


class TailorResumeRequest(BaseModel):
    job_id: str
    evidence_ids: list[str] = []
    target_category: str = "project"


# ---- Agent ----

class AgentRequest(BaseModel):
    message: str
    context: dict = {}
    max_iterations: int = 10


class AgentStepResponse(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: str


class AgentResponse(BaseModel):
    answer: str
    steps: list[AgentStepResponse] = []
    success: bool = True
    error: str = ""
