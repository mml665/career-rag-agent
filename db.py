from __future__ import annotations

import json
import sqlite3
from pathlib import Path


# Fields that are stored as JSON arrays/objects in SQLite
_JSON_FIELDS: dict[str, set[str]] = {
    "profile_evidence": set(),
    "job_postings": {"required_skills", "preferred_skills", "internship_requirements"},
    "match_analyses": {
        "matched_requirements",
        "missing_requirements",
        "matched_preferred_skills",
        "missing_preferred_skills",
        "evidence_ids",
        "evidence_map",
        "resume_suggestions",
        "semantic_evidence_ids",
    },
    "resume_versions": set(),
    "applications": set(),
    "rag_history": {"sources"},
}

_BOOL_FIELDS: dict[str, set[str]] = {
    "profile_evidence": {"verified"},
    "match_analyses": {"is_stale"},
}


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    target_role TEXT NOT NULL DEFAULT '',
    preferred_locations TEXT NOT NULL DEFAULT '',
    homepage TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS profile_evidence (
    evidence_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    source_page INTEGER,
    verified INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS job_postings (
    job_id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    raw_description TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    required_skills TEXT NOT NULL DEFAULT '[]',
    preferred_skills TEXT NOT NULL DEFAULT '[]',
    internship_requirements TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS match_analyses (
    analysis_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0.0,
    matched_requirements TEXT NOT NULL DEFAULT '[]',
    missing_requirements TEXT NOT NULL DEFAULT '[]',
    matched_preferred_skills TEXT NOT NULL DEFAULT '[]',
    missing_preferred_skills TEXT NOT NULL DEFAULT '[]',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    evidence_map TEXT NOT NULL DEFAULT '{}',
    resume_suggestions TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT '',
    analysis_type TEXT NOT NULL DEFAULT 'keyword',
    keyword_score REAL,
    semantic_score REAL,
    semantic_evidence_ids TEXT NOT NULL DEFAULT '[]',
    model_explanation TEXT NOT NULL DEFAULT '',
    is_stale INTEGER NOT NULL DEFAULT 0,
    invalidated_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (job_id) REFERENCES job_postings(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    application_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    analysis_id TEXT NOT NULL DEFAULT '',
    resume_version TEXT NOT NULL DEFAULT '',
    resume_version_id TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (job_id) REFERENCES job_postings(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_versions (
    version_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    target_category TEXT NOT NULL DEFAULT 'project',
    fit_assessment TEXT NOT NULL DEFAULT '',
    evidence_basis TEXT NOT NULL DEFAULT '',
    gap_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (job_id) REFERENCES job_postings(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rag_history (
    history_id TEXT PRIMARY KEY,
    time TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]'
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    # ---- CandidateProfile (singleton) ----

    def get_profile(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
            if row is None:
                return {}
            row_dict = dict(row)
            row_dict.pop("id", None)
            return self._row_to_dict("candidate_profile", row_dict)

    def save_profile(self, data: dict) -> dict:
        fields = data.copy()
        row = self._dict_to_row("candidate_profile", fields)
        with self._connect() as conn:
            conn.execute("DELETE FROM candidate_profile WHERE id = 1")
            cols = list(row.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            conn.execute(
                f"INSERT INTO candidate_profile (id, {col_names}) VALUES (1, {placeholders})",
                [row[c] for c in cols],
            )
        return fields

    # ---- ProfileEvidence ----

    def list_evidence(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profile_evidence ORDER BY created_at").fetchall()
            return [self._row_to_dict("profile_evidence", dict(r)) for r in rows]

    def add_evidence(self, data: dict) -> dict:
        row = self._dict_to_row("profile_evidence", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO profile_evidence ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def update_evidence(self, evidence_id: str, data: dict) -> dict:
        row = self._dict_to_row("profile_evidence", data)
        set_clause = ", ".join(f"{k} = ?" for k in row)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE profile_evidence SET {set_clause} WHERE evidence_id = ?",
                [*row.values(), evidence_id],
            )
        return data

    def delete_evidence(self, evidence_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM profile_evidence WHERE evidence_id = ?", (evidence_id,))
            return cursor.rowcount > 0

    # ---- JobPosting ----

    def list_jobs(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM job_postings ORDER BY created_at").fetchall()
            return [self._row_to_dict("job_postings", dict(r)) for r in rows]

    def add_job(self, data: dict) -> dict:
        row = self._dict_to_row("job_postings", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO job_postings ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def delete_job(self, job_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM job_postings WHERE job_id = ?", (job_id,))
            return cursor.rowcount > 0

    # ---- MatchAnalysis ----

    def list_analyses(self, job_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if job_id is None:
                rows = conn.execute("SELECT * FROM match_analyses ORDER BY created_at").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM match_analyses WHERE job_id = ? ORDER BY created_at",
                    (job_id,),
                ).fetchall()
            return [self._row_to_dict("match_analyses", dict(r)) for r in rows]

    def add_analysis(self, data: dict) -> dict:
        row = self._dict_to_row("match_analyses", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO match_analyses ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def update_analysis(self, analysis_id: str, data: dict) -> dict:
        row = self._dict_to_row("match_analyses", data)
        set_clause = ", ".join(f"{k} = ?" for k in row)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE match_analyses SET {set_clause} WHERE analysis_id = ?",
                [*row.values(), analysis_id],
            )
        return data

    def delete_analysis(self, analysis_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM match_analyses WHERE analysis_id = ?", (analysis_id,)
            )
            return cursor.rowcount > 0

    def invalidate_all_analyses(self) -> None:
        from datetime import datetime

        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE match_analyses SET is_stale = 1, invalidated_at = ? WHERE is_stale = 0",
                (timestamp,),
            )

    # ---- ResumeVersion ----

    def list_versions(self, job_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if job_id is None:
                rows = conn.execute("SELECT * FROM resume_versions ORDER BY created_at").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM resume_versions WHERE job_id = ? ORDER BY created_at",
                    (job_id,),
                ).fetchall()
            return [self._row_to_dict("resume_versions", dict(r)) for r in rows]

    def add_version(self, data: dict) -> dict:
        row = self._dict_to_row("resume_versions", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO resume_versions ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def delete_version(self, version_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM resume_versions WHERE version_id = ?", (version_id,)
            )
            if cursor.rowcount > 0:
                conn.execute(
                    "UPDATE applications SET resume_version_id = '' WHERE resume_version_id = ?",
                    (version_id,),
                )
                return True
            return False

    # ---- ApplicationRecord ----

    def list_applications(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM applications ORDER BY created_at").fetchall()
            return [self._row_to_dict("applications", dict(r)) for r in rows]

    def add_application(self, data: dict) -> dict:
        row = self._dict_to_row("applications", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO applications ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def update_application(self, application_id: str, data: dict) -> dict:
        row = self._dict_to_row("applications", data)
        set_clause = ", ".join(f"{k} = ?" for k in row)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE applications SET {set_clause} WHERE application_id = ?",
                [*row.values(), application_id],
            )
        return data

    def delete_application(self, application_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM applications WHERE application_id = ?", (application_id,)
            )
            return cursor.rowcount > 0

    # ---- rag_history ----

    def list_history(self, limit: int | None = None) -> list[dict]:
        with self._connect() as conn:
            if limit is None:
                rows = conn.execute("SELECT * FROM rag_history ORDER BY time DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rag_history ORDER BY time DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._row_to_dict("rag_history", dict(r)) for r in rows]

    def add_history(self, data: dict) -> dict:
        row = self._dict_to_row("rag_history", data)
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO rag_history ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
        return data

    def delete_history(self, history_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM rag_history WHERE history_id = ?", (history_id,)
            )
            return cursor.rowcount > 0

    def clear_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM rag_history")

    # ---- Helpers ----

    @classmethod
    def _row_to_dict(cls, table: str, row: dict) -> dict:
        json_fields = _JSON_FIELDS.get(table, set())
        bool_fields = _BOOL_FIELDS.get(table, set())
        result = {}
        for k, v in row.items():
            if k in json_fields and isinstance(v, str):
                result[k] = json.loads(v)
            elif k in bool_fields:
                result[k] = bool(v)
            else:
                result[k] = v
        return result

    @classmethod
    def _dict_to_row(cls, table: str, data: dict) -> dict:
        json_fields = _JSON_FIELDS.get(table, set())
        bool_fields = _BOOL_FIELDS.get(table, set())
        row = {}
        for k, v in data.items():
            if k in json_fields:
                row[k] = json.dumps(v, ensure_ascii=False)
            elif k in bool_fields:
                row[k] = int(v)
            else:
                row[k] = v
        return row
