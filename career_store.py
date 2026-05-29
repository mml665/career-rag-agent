from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4


PROFILE_CATEGORIES = {
    "education": "教育背景",
    "skill": "技能",
    "project": "项目经历",
    "award": "奖项/成果",
    "availability": "实习条件",
}

APPLICATION_STATUSES = {
    "planned": "准备投递",
    "submitted": "已投递",
    "written_test": "笔试",
    "interview": "面试",
    "offer": "Offer",
    "closed": "结束",
}


@dataclass
class ProfileEvidence:
    evidence_id: str
    category: str
    content: str
    title: str = ""
    source_file: str = ""
    source_page: int | None = None
    verified: bool = True
    created_at: str = ""


@dataclass
class CandidateProfile:
    name: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    target_role: str = ""
    preferred_locations: str = ""
    homepage: str = ""
    summary: str = ""
    updated_at: str = ""


@dataclass
class JobPosting:
    job_id: str
    company: str
    title: str
    location: str
    raw_description: str
    source_url: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    internship_requirements: list[str] = field(default_factory=list)
    created_at: str = ""


@dataclass
class MatchAnalysis:
    analysis_id: str
    job_id: str
    score: float
    matched_requirements: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    matched_preferred_skills: list[str] = field(default_factory=list)
    missing_preferred_skills: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    evidence_map: dict[str, list[str]] = field(default_factory=dict)
    resume_suggestions: list[str] = field(default_factory=list)
    created_at: str = ""
    analysis_type: str = "keyword"
    keyword_score: float | None = None
    semantic_score: float | None = None
    semantic_evidence_ids: list[str] = field(default_factory=list)
    model_explanation: str = ""
    is_stale: bool = False
    invalidated_at: str = ""


@dataclass
class ApplicationRecord:
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


@dataclass
class ResumeVersion:
    version_id: str
    job_id: str
    name: str
    content: str
    target_category: str = "project"
    fit_assessment: str = ""
    evidence_basis: str = ""
    gap_notes: str = ""
    created_at: str = ""


class CareerStore:
    def __init__(
        self,
        data_dir: Path = Path("data/career"),
        db_path: Path | None = None,
    ):
        self.data_dir = data_dir
        self._db = None

        if db_path is not None:
            from db import Database
            self._db = Database(db_path)
        else:
            self.candidate_profile_path = data_dir / "candidate_profile.json"
            self.profile_path = data_dir / "profile_evidence.json"
            self.jobs_path = data_dir / "job_postings.json"
            self.analyses_path = data_dir / "match_analyses.json"
            self.applications_path = data_dir / "application_records.json"
            self.resume_versions_path = data_dir / "resume_versions.json"
            self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_candidate_profile(self) -> CandidateProfile:
        if self._db:
            payload = self._db.get_profile()
            return CandidateProfile(**payload) if payload else CandidateProfile()
        if not self.candidate_profile_path.exists():
            return CandidateProfile()
        payload = json.loads(self.candidate_profile_path.read_text(encoding="utf-8"))
        return CandidateProfile(**payload)

    def save_candidate_profile(
        self,
        *,
        name: str = "",
        phone: str = "",
        email: str = "",
        city: str = "",
        target_role: str = "",
        preferred_locations: str = "",
        homepage: str = "",
        summary: str = "",
    ) -> CandidateProfile:
        profile = CandidateProfile(
            name=name.strip(),
            phone=phone.strip(),
            email=email.strip(),
            city=city.strip(),
            target_role=target_role.strip(),
            preferred_locations=preferred_locations.strip(),
            homepage=homepage.strip(),
            summary=summary.strip(),
            updated_at=self._timestamp(),
        )
        if self._db:
            self._db.save_profile(asdict(profile))
        else:
            self.candidate_profile_path.write_text(
                json.dumps(asdict(profile), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return profile

    def add_profile_evidence(
        self,
        *,
        category: str,
        content: str,
        title: str = "",
        source_file: str = "",
        source_page: int | None = None,
        verified: bool = True,
    ) -> ProfileEvidence:
        if category not in PROFILE_CATEGORIES:
            raise ValueError("不支持的履历证据类别。")
        if not content.strip():
            raise ValueError("事实描述不能为空。")

        evidence = ProfileEvidence(
            evidence_id=self._new_id("evidence"),
            category=category,
            content=content.strip(),
            title=title.strip(),
            source_file=source_file.strip(),
            source_page=source_page,
            verified=verified,
            created_at=self._timestamp(),
        )
        if self._db:
            self._db.add_evidence(asdict(evidence))
            self._db.invalidate_all_analyses()
        else:
            items = self.list_profile_evidence()
            items.append(evidence)
            self._write_records(self.profile_path, [asdict(item) for item in items])
            self._invalidate_match_analyses()
        return evidence

    def list_profile_evidence(self) -> list[ProfileEvidence]:
        if self._db:
            return [ProfileEvidence(**item) for item in self._db.list_evidence()]
        return [ProfileEvidence(**item) for item in self._read_records(self.profile_path)]

    def save_profile_sections(
        self,
        sections: dict[str, str],
        *,
        source_file: str = "",
        verified: bool = True,
    ) -> list[ProfileEvidence]:
        if any(category not in PROFILE_CATEGORIES for category in sections):
            raise ValueError("不支持的履历证据类别。")
        cleaned_sections = {
            category: sections.get(category, "").strip() for category in PROFILE_CATEGORIES
        }
        existing_records = self.list_profile_evidence()
        existing_by_category: dict[str, ProfileEvidence] = {}
        for evidence in existing_records:
            existing_by_category.setdefault(evidence.category, evidence)

        timestamp = self._timestamp()
        records: list[ProfileEvidence] = []
        for category, content in cleaned_sections.items():
            if not content:
                continue
            existing = existing_by_category.get(category)
            records.append(
                ProfileEvidence(
                    evidence_id=existing.evidence_id if existing else self._new_id("evidence"),
                    category=category,
                    content=content,
                    source_file=source_file.strip(),
                    verified=verified,
                    created_at=existing.created_at if existing else timestamp,
                )
            )

        if self._db:
            old_payload = [asdict(item) for item in existing_records]
            new_payload = [asdict(item) for item in records]
            for record in records:
                existing = next(
                    (e for e in existing_records if e.evidence_id == record.evidence_id), None
                )
                if existing:
                    self._db.update_evidence(record.evidence_id, asdict(record))
                else:
                    self._db.add_evidence(asdict(record))
            if old_payload != new_payload:
                self._db.invalidate_all_analyses()
        else:
            old_payload = [asdict(item) for item in existing_records]
            new_payload = [asdict(item) for item in records]
            self._write_records(self.profile_path, new_payload)
            if old_payload != new_payload:
                self._invalidate_match_analyses()
        return records

    def update_profile_evidence(
        self,
        evidence_id: str,
        *,
        category: str,
        content: str,
        source_file: str = "",
        source_page: int | None = None,
        verified: bool = True,
    ) -> ProfileEvidence:
        if category not in PROFILE_CATEGORIES:
            raise ValueError("不支持的履历证据类别。")
        if not content.strip():
            raise ValueError("事实描述不能为空。")

        items = self.list_profile_evidence()
        existing = next((item for item in items if item.evidence_id == evidence_id), None)
        if existing is None:
            raise ValueError("未找到需要编辑的履历证据。")
        updated = ProfileEvidence(
            evidence_id=existing.evidence_id,
            category=category,
            content=content.strip(),
            source_file=source_file.strip(),
            source_page=source_page,
            verified=verified,
            created_at=existing.created_at,
        )
        if self._db:
            self._db.update_evidence(evidence_id, asdict(updated))
            self._db.invalidate_all_analyses()
        else:
            records = [updated if item.evidence_id == evidence_id else item for item in items]
            self._write_records(self.profile_path, [asdict(item) for item in records])
            self._invalidate_match_analyses()
        return updated

    def delete_profile_evidence(self, evidence_id: str) -> bool:
        items = self.list_profile_evidence()
        kept = [item for item in items if item.evidence_id != evidence_id]
        if len(kept) == len(items):
            return False
        if self._db:
            self._db.delete_evidence(evidence_id)
            self._db.invalidate_all_analyses()
        else:
            self._write_records(self.profile_path, [asdict(item) for item in kept])
            self._invalidate_match_analyses()
        return True

    def delete_profile_section(self, category: str) -> bool:
        if category not in PROFILE_CATEGORIES:
            raise ValueError("不支持的履历证据类别。")
        items = self.list_profile_evidence()
        kept = [item for item in items if item.category != category]
        if len(kept) == len(items):
            return False
        if self._db:
            for item in items:
                if item.category == category:
                    self._db.delete_evidence(item.evidence_id)
            self._db.invalidate_all_analyses()
        else:
            self._write_records(self.profile_path, [asdict(item) for item in kept])
            self._invalidate_match_analyses()
        return True

    def add_job_posting(
        self,
        *,
        company: str,
        title: str,
        location: str,
        raw_description: str,
        source_url: str = "",
        required_skills: list[str] | None = None,
        preferred_skills: list[str] | None = None,
        internship_requirements: list[str] | None = None,
    ) -> JobPosting:
        if not company.strip() or not title.strip() or not raw_description.strip():
            raise ValueError("公司、岗位名称和 JD 原文不能为空。")

        job = JobPosting(
            job_id=self._new_id("job"),
            company=company.strip(),
            title=title.strip(),
            location=location.strip(),
            source_url=source_url.strip(),
            raw_description=raw_description.strip(),
            required_skills=self._unique_items(required_skills or []),
            preferred_skills=self._unique_items(preferred_skills or []),
            internship_requirements=self._unique_items(internship_requirements or []),
            created_at=self._timestamp(),
        )
        if self._db:
            self._db.add_job(asdict(job))
        else:
            items = self.list_job_postings()
            items.append(job)
            self._write_records(self.jobs_path, [asdict(item) for item in items])
        return job

    def list_job_postings(self) -> list[JobPosting]:
        if self._db:
            return [JobPosting(**item) for item in self._db.list_jobs()]
        return [JobPosting(**item) for item in self._read_records(self.jobs_path)]

    def delete_job_posting(self, job_id: str) -> bool:
        if self._db:
            return self._db.delete_job(job_id)
        items = self.list_job_postings()
        kept = [item for item in items if item.job_id != job_id]
        if len(kept) == len(items):
            return False
        self._write_records(self.jobs_path, [asdict(item) for item in kept])
        analyses = [item for item in self.list_match_analyses() if item.job_id != job_id]
        self._write_records(self.analyses_path, [asdict(item) for item in analyses])
        applications = [item for item in self.list_applications() if item.job_id != job_id]
        self._write_records(self.applications_path, [asdict(item) for item in applications])
        versions = [item for item in self.list_resume_versions() if item.job_id != job_id]
        self._write_records(self.resume_versions_path, [asdict(item) for item in versions])
        return True

    def analyze_job_match(self, job_id: str) -> MatchAnalysis:
        job = next((item for item in self.list_job_postings() if item.job_id == job_id), None)
        if job is None:
            raise ValueError("未找到需要分析的岗位。")

        verified_evidence = [item for item in self.list_profile_evidence() if item.verified]
        matched_required, missing_required, required_map = self._match_skills(
            job.required_skills, verified_evidence
        )
        matched_preferred, missing_preferred, preferred_map = self._match_skills(
            job.preferred_skills, verified_evidence
        )
        evidence_map = {**required_map, **preferred_map}
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for matched_ids in evidence_map.values()
                for evidence_id in matched_ids
            )
        )
        analysis = MatchAnalysis(
            analysis_id=self._new_id("analysis"),
            job_id=job_id,
            score=self._skill_score(
                matched_required,
                job.required_skills,
                matched_preferred,
                job.preferred_skills,
            ),
            matched_requirements=matched_required,
            missing_requirements=missing_required,
            matched_preferred_skills=matched_preferred,
            missing_preferred_skills=missing_preferred,
            evidence_ids=evidence_ids,
            evidence_map=evidence_map,
            resume_suggestions=self._resume_suggestions(
                matched_required,
                matched_preferred,
                missing_required,
                verified_evidence,
            ),
            created_at=self._timestamp(),
            keyword_score=self._skill_score(
                matched_required,
                job.required_skills,
                matched_preferred,
                job.preferred_skills,
            ),
        )
        if self._db:
            self._db.add_analysis(asdict(analysis))
        else:
            items = self.list_match_analyses()
            items.append(analysis)
            self._write_records(self.analyses_path, [asdict(item) for item in items])
        return analysis

    def list_match_analyses(self, job_id: str | None = None) -> list[MatchAnalysis]:
        if self._db:
            return [MatchAnalysis(**item) for item in self._db.list_analyses(job_id)]
        items = [MatchAnalysis(**item) for item in self._read_records(self.analyses_path)]
        if job_id is None:
            return items
        return [item for item in items if item.job_id == job_id]

    def delete_match_analysis(self, analysis_id: str) -> bool:
        if self._db:
            return self._db.delete_analysis(analysis_id)
        items = self.list_match_analyses()
        kept = [item for item in items if item.analysis_id != analysis_id]
        if len(kept) == len(items):
            return False
        self._write_records(self.analyses_path, [asdict(item) for item in kept])
        return True

    def enhance_match_analysis(
        self,
        analysis_id: str,
        *,
        semantic_score: float,
        semantic_evidence_ids: list[str],
        model_explanation: str,
    ) -> MatchAnalysis:
        items = self.list_match_analyses()
        analysis = next((item for item in items if item.analysis_id == analysis_id), None)
        if analysis is None:
            raise ValueError("未找到需要增强的匹配分析。")
        keyword_score = analysis.keyword_score if analysis.keyword_score is not None else analysis.score
        analysis.score = round(keyword_score * 0.6 + semantic_score * 0.4, 1)
        analysis.analysis_type = "hybrid"
        analysis.keyword_score = keyword_score
        analysis.semantic_score = semantic_score
        analysis.semantic_evidence_ids = list(dict.fromkeys(semantic_evidence_ids))
        analysis.model_explanation = model_explanation.strip()

        if self._db:
            self._db.update_analysis(analysis_id, asdict(analysis))
        else:
            self._write_records(self.analyses_path, [asdict(item) for item in items])
        return analysis

    def add_resume_version(
        self,
        *,
        job_id: str,
        name: str,
        content: str,
        target_category: str = "project",
        fit_assessment: str = "",
        evidence_basis: str = "",
        gap_notes: str = "",
    ) -> ResumeVersion:
        if not any(item.job_id == job_id for item in self.list_job_postings()):
            raise ValueError("未找到对应的岗位。")
        if target_category not in PROFILE_CATEGORIES:
            raise ValueError("不支持的简历栏目。")
        if not name.strip() or not content.strip():
            raise ValueError("版本名称和简历内容不能为空。")
        version = ResumeVersion(
            version_id=self._new_id("version"),
            job_id=job_id,
            name=name.strip(),
            content=content.strip(),
            target_category=target_category,
            fit_assessment=fit_assessment.strip(),
            evidence_basis=evidence_basis.strip(),
            gap_notes=gap_notes.strip(),
            created_at=self._timestamp(),
        )
        if self._db:
            self._db.add_version(asdict(version))
        else:
            items = self.list_resume_versions()
            items.append(version)
            self._write_records(self.resume_versions_path, [asdict(item) for item in items])
        return version

    def list_resume_versions(self, job_id: str | None = None) -> list[ResumeVersion]:
        if self._db:
            return [ResumeVersion(**item) for item in self._db.list_versions(job_id)]
        items = [ResumeVersion(**item) for item in self._read_records(self.resume_versions_path)]
        if job_id is None:
            return items
        return [item for item in items if item.job_id == job_id]

    def delete_resume_version(self, version_id: str) -> bool:
        if self._db:
            return self._db.delete_version(version_id)
        items = self.list_resume_versions()
        kept = [item for item in items if item.version_id != version_id]
        if len(kept) == len(items):
            return False
        self._write_records(self.resume_versions_path, [asdict(item) for item in kept])
        applications = self.list_applications()
        if any(item.resume_version_id == version_id for item in applications):
            for application in applications:
                if application.resume_version_id == version_id:
                    application.resume_version_id = ""
            self._write_records(self.applications_path, [asdict(item) for item in applications])
        return True

    def add_application(
        self,
        *,
        job_id: str,
        status: str = "planned",
        analysis_id: str = "",
        resume_version: str = "",
        resume_version_id: str = "",
        submitted_at: str = "",
        notes: str = "",
    ) -> ApplicationRecord:
        self._validate_application(job_id, status)
        timestamp = self._timestamp()
        record = ApplicationRecord(
            application_id=self._new_id("application"),
            job_id=job_id,
            status=status,
            analysis_id=analysis_id.strip(),
            resume_version=resume_version.strip(),
            resume_version_id=resume_version_id.strip(),
            submitted_at=submitted_at.strip(),
            notes=notes.strip(),
            created_at=timestamp,
            updated_at=timestamp,
        )
        if self._db:
            self._db.add_application(asdict(record))
        else:
            items = self.list_applications()
            items.append(record)
            self._write_records(self.applications_path, [asdict(item) for item in items])
        return record

    def list_applications(self) -> list[ApplicationRecord]:
        if self._db:
            return [ApplicationRecord(**item) for item in self._db.list_applications()]
        return [ApplicationRecord(**item) for item in self._read_records(self.applications_path)]

    def update_application(
        self,
        application_id: str,
        *,
        status: str,
        resume_version: str = "",
        resume_version_id: str = "",
        submitted_at: str = "",
        notes: str = "",
    ) -> ApplicationRecord:
        items = self.list_applications()
        existing = next(
            (item for item in items if item.application_id == application_id), None
        )
        if existing is None:
            raise ValueError("未找到需要更新的投递记录。")
        self._validate_application(existing.job_id, status)
        updated = ApplicationRecord(
            application_id=existing.application_id,
            job_id=existing.job_id,
            status=status,
            analysis_id=existing.analysis_id,
            resume_version=resume_version.strip(),
            resume_version_id=resume_version_id.strip(),
            submitted_at=submitted_at.strip(),
            notes=notes.strip(),
            created_at=existing.created_at,
            updated_at=self._timestamp(),
        )
        if self._db:
            self._db.update_application(application_id, asdict(updated))
        else:
            records = [updated if item.application_id == application_id else item for item in items]
            self._write_records(self.applications_path, [asdict(item) for item in records])
        return updated

    def delete_application(self, application_id: str) -> bool:
        if self._db:
            return self._db.delete_application(application_id)
        items = self.list_applications()
        kept = [item for item in items if item.application_id != application_id]
        if len(kept) == len(items):
            return False
        self._write_records(self.applications_path, [asdict(item) for item in kept])
        return True

    @classmethod
    def _match_skills(
        cls, skills: list[str], evidence: list[ProfileEvidence]
    ) -> tuple[list[str], list[str], dict[str, list[str]]]:
        matched: list[str] = []
        missing: list[str] = []
        evidence_map: dict[str, list[str]] = {}
        for skill in skills:
            needle = cls._normalize_text(skill)
            matches = [
                item
                for item in evidence
                if needle and needle in cls._normalize_text(item.content)
            ]
            if matches:
                matched.append(skill)
                evidence_map[skill] = [item.evidence_id for item in matches]
            else:
                missing.append(skill)
        return matched, missing, evidence_map

    @staticmethod
    def _skill_score(
        matched_required: list[str],
        required_skills: list[str],
        matched_preferred: list[str],
        preferred_skills: list[str],
    ) -> float:
        required_ratio = len(matched_required) / len(required_skills) if required_skills else None
        preferred_ratio = len(matched_preferred) / len(preferred_skills) if preferred_skills else None
        if required_ratio is not None and preferred_ratio is not None:
            return round((required_ratio * 0.7 + preferred_ratio * 0.3) * 100, 1)
        if required_ratio is not None:
            return round(required_ratio * 100, 1)
        if preferred_ratio is not None:
            return round(preferred_ratio * 100, 1)
        return 0.0

    @staticmethod
    def _resume_suggestions(
        matched_required: list[str],
        matched_preferred: list[str],
        missing_required: list[str],
        evidence: list[ProfileEvidence],
    ) -> list[str]:
        suggestions: list[str] = []
        matched = matched_required + matched_preferred
        if matched:
            suggestions.append(f"简历优先呈现可证明这些技能的经历：{', '.join(matched)}。")
        if missing_required:
            suggestions.append(f"当前证据尚未覆盖必备技能：{', '.join(missing_required)}。")
        if not evidence:
            suggestions.append("请先录入并确认可用于简历的真实履历证据。")
        return suggestions

    @staticmethod
    def _read_records(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_records(path: Path, records: list[dict]) -> None:
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", "", value).casefold()

    @staticmethod
    def _unique_items(items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items if item.strip()]
        return list(dict.fromkeys(cleaned))

    def _invalidate_match_analyses(self) -> None:
        analyses = self.list_match_analyses()
        if not analyses:
            return
        timestamp = self._timestamp()
        changed = False
        for analysis in analyses:
            if not analysis.is_stale:
                analysis.is_stale = True
                analysis.invalidated_at = timestamp
                changed = True
        if changed:
            self._write_records(self.analyses_path, [asdict(item) for item in analyses])

    def _validate_application(self, job_id: str, status: str) -> None:
        if status not in APPLICATION_STATUSES:
            raise ValueError("不支持的投递状态。")
        if not any(item.job_id == job_id for item in self.list_job_postings()):
            raise ValueError("未找到对应的岗位。")
