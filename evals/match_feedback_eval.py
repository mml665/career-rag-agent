from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


def summarize_feedback(records: Iterable[dict]) -> dict:
    feedback = [item for item in records if isinstance(item, dict)]
    total = len(feedback)
    if total == 0:
        return {
            "feedback_count": 0,
            "accuracy_proxy": 0.0,
            "issue_distribution": {},
            "actionable_cases": [],
        }

    ratings = Counter(str(item.get("rating", "")) for item in feedback)
    issues = Counter(str(item.get("issue_type", "") or "none") for item in feedback)
    actionable = [
        {
            "feedback_id": item.get("feedback_id", ""),
            "analysis_id": item.get("analysis_id", ""),
            "rating": item.get("rating", ""),
            "issue_type": item.get("issue_type", ""),
            "comment": item.get("comment", ""),
            "correction": item.get("correction", ""),
        }
        for item in feedback
        if item.get("rating") in {"partially_accurate", "wrong"}
        or item.get("issue_type") in {"missed_skill", "hallucination", "wrong_citation"}
    ]

    return {
        "feedback_count": total,
        "accuracy_proxy": round(ratings.get("accurate", 0) / total, 4),
        "issue_distribution": dict(issues),
        "actionable_cases": actionable,
    }


def _load_records(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("feedback", [])
    if isinstance(payload, list):
        return payload
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize match feedback bad cases")
    parser.add_argument("--input", type=Path, default=Path("data/career/match_feedback.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = summarize_feedback(_load_records(args.input) if args.input.exists() else [])
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
