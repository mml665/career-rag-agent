from __future__ import annotations

from pathlib import Path

import requests

from career_store import (
    ApplicationRecord,
    CandidateProfile,
    JobPosting,
    MatchAnalysis,
    ProfileEvidence,
    ResumeVersion,
)


class CareerApiClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def load_candidate_profile(self) -> CandidateProfile:
        resp = requests.get(f"{self.base_url}/api/profile")
        resp.raise_for_status()
        return CandidateProfile(**resp.json())

    def save_candidate_profile(self, **kwargs) -> CandidateProfile:
        resp = requests.post(f"{self.base_url}/api/profile", json=kwargs)
        resp.raise_for_status()
        return CandidateProfile(**resp.json())

    def list_profile_evidence(self) -> list[ProfileEvidence]:
        resp = requests.get(f"{self.base_url}/api/evidence")
        resp.raise_for_status()
        return [ProfileEvidence(**item) for item in resp.json()]

    def add_profile_evidence(self, **kwargs) -> ProfileEvidence:
        resp = requests.post(f"{self.base_url}/api/evidence", json=kwargs)
        resp.raise_for_status()
        return ProfileEvidence(**resp.json())

    def update_profile_evidence(self, evidence_id: str, **kwargs) -> ProfileEvidence:
        resp = requests.put(f"{self.base_url}/api/evidence/{evidence_id}", json=kwargs)
        resp.raise_for_status()
        return ProfileEvidence(**resp.json())

    def delete_profile_evidence(self, evidence_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/evidence/{evidence_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def save_profile_sections(self, sections: dict[str, str], **kwargs) -> list[ProfileEvidence]:
        payload = {"sections": sections, **kwargs}
        resp = requests.post(f"{self.base_url}/api/evidence/sections", json=payload)
        resp.raise_for_status()
        return [ProfileEvidence(**item) for item in resp.json()]

    def delete_profile_section(self, category: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/evidence/section/{category}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def list_job_postings(self) -> list[JobPosting]:
        resp = requests.get(f"{self.base_url}/api/jobs")
        resp.raise_for_status()
        return [JobPosting(**item) for item in resp.json()]

    def add_job_posting(self, **kwargs) -> JobPosting:
        resp = requests.post(f"{self.base_url}/api/jobs", json=kwargs)
        resp.raise_for_status()
        return JobPosting(**resp.json())

    def delete_job_posting(self, job_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/jobs/{job_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def list_match_analyses(self, job_id: str | None = None) -> list[MatchAnalysis]:
        params = {}
        if job_id is not None:
            params["job_id"] = job_id
        resp = requests.get(f"{self.base_url}/api/analyses", params=params)
        resp.raise_for_status()
        return [MatchAnalysis(**item) for item in resp.json()]

    def analyze_job_match(self, job_id: str) -> MatchAnalysis:
        resp = requests.post(f"{self.base_url}/api/analyses", params={"job_id": job_id})
        resp.raise_for_status()
        return MatchAnalysis(**resp.json())

    def enhance_match_analysis(self, analysis_id: str, **kwargs) -> MatchAnalysis:
        resp = requests.put(f"{self.base_url}/api/analyses/{analysis_id}", json=kwargs)
        resp.raise_for_status()
        return MatchAnalysis(**resp.json())

    def delete_match_analysis(self, analysis_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/analyses/{analysis_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def list_resume_versions(self, job_id: str | None = None) -> list[ResumeVersion]:
        params = {}
        if job_id is not None:
            params["job_id"] = job_id
        resp = requests.get(f"{self.base_url}/api/resume-versions", params=params)
        resp.raise_for_status()
        return [ResumeVersion(**item) for item in resp.json()]

    def add_resume_version(self, **kwargs) -> ResumeVersion:
        resp = requests.post(f"{self.base_url}/api/resume-versions", json=kwargs)
        resp.raise_for_status()
        return ResumeVersion(**resp.json())

    def delete_resume_version(self, version_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/resume-versions/{version_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def list_applications(self) -> list[ApplicationRecord]:
        resp = requests.get(f"{self.base_url}/api/applications")
        resp.raise_for_status()
        return [ApplicationRecord(**item) for item in resp.json()]

    def add_application(self, **kwargs) -> ApplicationRecord:
        resp = requests.post(f"{self.base_url}/api/applications", json=kwargs)
        resp.raise_for_status()
        return ApplicationRecord(**resp.json())

    def update_application(self, application_id: str, **kwargs) -> ApplicationRecord:
        resp = requests.put(f"{self.base_url}/api/applications/{application_id}", json=kwargs)
        resp.raise_for_status()
        return ApplicationRecord(**resp.json())

    def delete_application(self, application_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/api/applications/{application_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True


class RagApiClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        enable_bm25: bool = True,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        rrf_k: int = 60,
        enable_rerank: bool = True,
        rerank_top_n: int = 10,
    ):
        self.base_url = base_url
        self._upload_dir: Path | None = None
        self.enable_bm25 = enable_bm25
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k
        self.enable_rerank = enable_rerank
        self.rerank_top_n = rerank_top_n

    @property
    def upload_dir(self) -> Path:
        if self._upload_dir is None:
            try:
                resp = requests.get(f"{self.base_url}/api/library/upload-dir")
                resp.raise_for_status()
                self._upload_dir = Path(resp.json()["upload_dir"])
            except Exception:
                self._upload_dir = Path("data/uploads")
        return self._upload_dir

    def is_configured(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/library/configured")
            resp.raise_for_status()
            return resp.json().get("configured", False)
        except requests.ConnectionError:
            return False

    def ask(self, question: str, top_k: int = 4) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/library/ask",
            json={"question": question, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        resp = requests.get(
            f"{self.base_url}/api/library/search",
            params={"question": question, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()

    def ingest_all(self) -> int:
        resp = requests.post(
            f"{self.base_url}/api/library/index",
            json={
                "enable_bm25": self.enable_bm25,
                "bm25_weight": self.bm25_weight,
                "vector_weight": self.vector_weight,
                "rrf_k": self.rrf_k,
                "enable_rerank": self.enable_rerank,
                "rerank_top_n": self.rerank_top_n,
            },
        )
        resp.raise_for_status()
        return resp.json().get("count", 0)

    def save_upload(self, filename: str, content: bytes) -> None:
        resp = requests.post(
            f"{self.base_url}/api/library/upload",
            files={"file": (filename, content)},
        )
        resp.raise_for_status()

    def list_documents(self) -> list[dict]:
        resp = requests.get(f"{self.base_url}/api/library/documents")
        resp.raise_for_status()
        return resp.json()

    def delete_document(self, path: str) -> None:
        resp = requests.delete(f"{self.base_url}/api/library/documents/{path}")
        resp.raise_for_status()

    def clear_uploads(self) -> None:
        resp = requests.delete(f"{self.base_url}/api/library/documents")
        resp.raise_for_status()

    def reset_index(self) -> None:
        pass

    def summarize(self) -> dict:
        resp = requests.post(f"{self.base_url}/api/library/summarize")
        resp.raise_for_status()
        return resp.json()

    def extract_resume_upload(self, filename: str, content: bytes):
        resp = requests.post(
            f"{self.base_url}/api/library/extract-resume",
            files={"file": (filename, content)},
        )
        resp.raise_for_status()
        return resp.json()

    def extract_job_upload(self, filename: str, content: bytes):
        resp = requests.post(
            f"{self.base_url}/api/library/extract-job-file",
            files={"file": (filename, content)},
        )
        resp.raise_for_status()
        return resp.json()

    def extract_job_posting_text(self, raw: str):
        resp = requests.post(
            f"{self.base_url}/api/library/extract-job-text",
            json={"raw_description": raw},
        )
        resp.raise_for_status()
        return resp.json()

    def analyze_semantic_match(
        self,
        *,
        job_description: str,
        evidence: list[tuple[str, str]],
        keyword_summary: str,
    ):
        resp = requests.post(
            f"{self.base_url}/api/library/semantic-match",
            json={
                "job_description": job_description,
                "evidence": evidence,
                "keyword_summary": keyword_summary,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def tailor_resume(
        self,
        *,
        job_description: str,
        evidence: list[str],
        current_text: str = "",
        request: str = "",
    ):
        resp = requests.post(
            f"{self.base_url}/api/library/tailor-resume",
            json={
                "job_description": job_description,
                "evidence": evidence,
                "current_text": current_text,
                "request": request,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def export_resume(self, format: str = "docx") -> bytes:
        resp = requests.post(
            f"{self.base_url}/api/library/export-resume",
            json={"format": format},
        )
        resp.raise_for_status()
        return resp.content

    def load_history(self, limit: int | None = None) -> list[dict]:
        params = {}
        if limit is not None:
            params["limit"] = limit
        resp = requests.get(f"{self.base_url}/api/library/history", params=params)
        resp.raise_for_status()
        return resp.json()

    def delete_history_record(self, history_id: str) -> None:
        resp = requests.delete(f"{self.base_url}/api/library/history/{history_id}")
        resp.raise_for_status()

    def clear_history(self) -> None:
        resp = requests.delete(f"{self.base_url}/api/library/history")
        resp.raise_for_status()

    def agent(self, message: str, context: dict = None, max_iterations: int = 10) -> dict:
        """调用 Agent 执行用户请求。"""
        payload = {"message": message, "max_iterations": max_iterations}
        if context:
            payload["context"] = context
        resp = requests.post(f"{self.base_url}/api/library/agent", json=payload)
        resp.raise_for_status()
        return resp.json()
