"""一次性迁移脚本：将 JSON 文件数据迁移到 SQLite 数据库。"""
from __future__ import annotations

import json
from pathlib import Path

from db import Database

CAREER_DIR = Path("data/career")
HISTORY_FILE = Path("data/history.jsonl")
DB_PATH = CAREER_DIR / "career.db"


def read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def migrate() -> None:
    db = Database(DB_PATH)

    # candidate_profile
    profile_path = CAREER_DIR / "candidate_profile.json"
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        db.save_profile(profile)
        print(f"candidate_profile: 1 条记录")

    # profile_evidence
    evidence_records = read_json(CAREER_DIR / "profile_evidence.json")
    for record in evidence_records:
        db.add_evidence(record)
    print(f"profile_evidence: {len(evidence_records)} 条记录")

    # job_postings
    job_records = read_json(CAREER_DIR / "job_postings.json")
    for record in job_records:
        db.add_job(record)
    print(f"job_postings: {len(job_records)} 条记录")

    # match_analyses
    analysis_records = read_json(CAREER_DIR / "match_analyses.json")
    for record in analysis_records:
        db.add_analysis(record)
    print(f"match_analyses: {len(analysis_records)} 条记录")

    # resume_versions
    version_records = read_json(CAREER_DIR / "resume_versions.json")
    for record in version_records:
        db.add_version(record)
    print(f"resume_versions: {len(version_records)} 条记录")

    # applications
    application_records = read_json(CAREER_DIR / "application_records.json")
    for record in application_records:
        db.add_application(record)
    print(f"applications: {len(application_records)} 条记录")

    # rag_history
    history_records = read_jsonl(HISTORY_FILE)
    for record in history_records:
        db.add_history(record)
    print(f"rag_history: {len(history_records)} 条记录")

    print(f"\n迁移完成！数据库文件：{DB_PATH}")


if __name__ == "__main__":
    migrate()
