from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def _normalise_source(value: object) -> str:
    """Normalise source names so local paths and report names can be compared."""
    text = str(value or "").strip().replace("\\", "/").lower()
    while text.startswith("./"):
        text = text[2:]
    return text


def _source_matches(candidate: object, expected: object) -> bool:
    candidate_name = _normalise_source(candidate)
    expected_name = _normalise_source(expected)
    if not candidate_name or not expected_name:
        return False
    return (
        candidate_name == expected_name
        or candidate_name.endswith("/" + expected_name)
        or expected_name.endswith("/" + candidate_name)
    )


def _result_source(result: object) -> object:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("source") or result.get("source_name") or result.get("file")
    return None


def _case_recall(results: list[object], relevant_sources: list[object], k: int) -> float:
    if not relevant_sources:
        return 0.0
    retrieved = results[:k]
    hits = sum(
        any(_source_matches(_result_source(item), expected) for item in retrieved)
        for expected in relevant_sources
    )
    return hits / len(relevant_sources)


def _case_reciprocal_rank(results: list[object], relevant_sources: list[object], k: int) -> float:
    for rank, item in enumerate(results[:k], start=1):
        if any(_source_matches(_result_source(item), expected) for expected in relevant_sources):
            return 1.0 / rank
    return 0.0


def evaluate_cases(
    golden_cases: Iterable[dict],
    result_records: Iterable[dict],
    k: int = 5,
) -> dict:
    """Calculate retrieval metrics from a labelled set and retrieved results.

    Each golden case contains ``id``, ``query`` and ``relevant_sources``. Each
    result record contains ``case_id`` and a ``results`` list. The function is
    intentionally independent of Chroma or an embedding provider so it can be
    used in CI with deterministic fixtures.
    """
    golden = list(golden_cases)
    by_id = {str(item.get("case_id")): item for item in result_records}
    per_case = []

    for case in golden:
        case_id = str(case.get("id", ""))
        record = by_id.get(case_id, {})
        results = record.get("results", []) if isinstance(record, dict) else []
        relevant = list(case.get("relevant_sources", []))
        recall = _case_recall(results, relevant, k)
        reciprocal_rank = _case_reciprocal_rank(results, relevant, k)
        per_case.append(
            {
                "case_id": case_id,
                "query": case.get("query", ""),
                "recall_at_k": round(recall, 4),
                "reciprocal_rank": round(reciprocal_rank, 4),
                "hit": recall > 0,
                "retrieved": [_result_source(item) for item in results[:k]],
            }
        )

    total = len(per_case)
    if total == 0:
        return {"cases": 0, "k": k, "recall_at_k": 0.0, "mrr_at_k": 0.0, "hit_rate_at_k": 0.0, "details": []}

    return {
        "cases": total,
        "k": k,
        "recall_at_k": round(sum(item["recall_at_k"] for item in per_case) / total, 4),
        "mrr_at_k": round(sum(item["reciprocal_rank"] for item in per_case) / total, 4),
        "hit_rate_at_k": round(sum(item["hit"] for item in per_case) / total, 4),
        "details": per_case,
    }


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_live(golden_cases: list[dict], k: int) -> list[dict]:
    """Run the current local retriever; no external LLM call is required."""
    from rag_agent import RagAssistant, RagConfig

    assistant = RagAssistant(RagConfig())
    records = []
    for case in golden_cases:
        results = assistant.search(case.get("query", ""), top_k=k)
        records.append({"case_id": case.get("id", ""), "results": results})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Career RAG retrieval quality")
    parser.add_argument("--golden", type=Path, default=Path(__file__).with_name("golden_set.json"))
    parser.add_argument("--results", type=Path, help="JSON file containing case_id/results records")
    parser.add_argument("--live", action="store_true", help="Run the local Chroma/BM25 retriever")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    golden_payload = _load_json(args.golden)
    golden_cases = golden_payload.get("cases", []) if isinstance(golden_payload, dict) else golden_payload
    if args.live:
        result_records = _run_live(golden_cases, args.k)
    elif args.results:
        result_payload = _load_json(args.results)
        result_records = result_payload.get("results", []) if isinstance(result_payload, dict) else result_payload
    else:
        parser.error("provide --results or --live")

    metrics = evaluate_cases(golden_cases, result_records, k=args.k)
    rendered = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

