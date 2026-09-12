from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.agent_eval import _run_live as run_agent_live
from evals.agent_eval import evaluate_agent_cases
from evals.retrieval_eval import _run_live as run_retrieval_live
from evals.retrieval_eval import evaluate_cases as evaluate_retrieval_cases


AGENT_TARGETS = {
    "pass_rate": 0.8,
    "tool_path_accuracy": 0.9,
    "tool_recall": 0.9,
    "tool_precision": 0.8,
    "answer_rule_pass_rate": 0.9,
}

RETRIEVAL_TARGETS = {
    "recall_at_k": 0.8,
    "mrr_at_k": 0.6,
    "hit_rate_at_k": 0.8,
}


def load_suites(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suites = payload.get("suites", []) if isinstance(payload, dict) else payload
    if not isinstance(suites, list):
        raise ValueError(f"{path} must contain a suites list")
    return suites


def _suite_cases(suite: dict) -> list[dict]:
    cases = suite.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError(f"suite {suite.get('id', '<unknown>')} cases must be a list")
    return cases


def confidence_note(case_count: int, risk_level: str) -> str:
    if case_count >= 50:
        scale = "large"
    elif case_count >= 20:
        scale = "medium"
    else:
        scale = "small"
    notes = {
        "seed": "种子集只能证明核心链路可回归，不能代表线上泛化表现。",
        "directional": "方向性评测覆盖了改写和相近意图，可用于观察调参趋势。",
        "regression": "回归集适合防止已知业务流程退化。",
        "robustness": "鲁棒性集用于暴露误调用、否定表达和异常输入处理问题。",
    }
    return f"{scale} sample; {notes.get(risk_level, '需结合样本来源和人工标注质量解读。')}"


def target_status(metrics: dict, targets: dict[str, float]) -> dict[str, dict]:
    status = {}
    for key, target in targets.items():
        value = float(metrics.get(key, 0.0))
        status[key] = {
            "value": round(value, 4),
            "target": target,
            "met": value >= target,
        }
    return status


def weighted_average(suite_metrics: Iterable[dict], metric_name: str) -> float:
    total_cases = 0
    weighted_sum = 0.0
    for metrics in suite_metrics:
        cases = int(metrics.get("cases", 0))
        total_cases += cases
        weighted_sum += float(metrics.get(metric_name, 0.0)) * cases
    if total_cases == 0:
        return 0.0
    return round(weighted_sum / total_cases, 4)


def summarize_agent_suites(suite_results: list[dict]) -> dict:
    metrics = [item["metrics"] for item in suite_results]
    total_cases = sum(int(item.get("cases", 0)) for item in metrics)
    return {
        "suites": len(suite_results),
        "cases": total_cases,
        "pass_rate": weighted_average(metrics, "pass_rate"),
        "success_accuracy": weighted_average(metrics, "success_accuracy"),
        "tool_path_accuracy": weighted_average(metrics, "tool_path_accuracy"),
        "answer_rule_pass_rate": weighted_average(metrics, "answer_rule_pass_rate"),
        "tool_precision": weighted_average(metrics, "tool_precision"),
        "tool_recall": weighted_average(metrics, "tool_recall"),
        "avg_tool_calls": weighted_average(metrics, "avg_tool_calls"),
        "target_status": target_status(
            {
                "pass_rate": weighted_average(metrics, "pass_rate"),
                "tool_path_accuracy": weighted_average(metrics, "tool_path_accuracy"),
                "tool_recall": weighted_average(metrics, "tool_recall"),
                "tool_precision": weighted_average(metrics, "tool_precision"),
                "answer_rule_pass_rate": weighted_average(metrics, "answer_rule_pass_rate"),
            },
            AGENT_TARGETS,
        ),
    }


def summarize_retrieval_suites(suite_results: list[dict]) -> dict:
    metrics = [item["metrics"] for item in suite_results]
    total_cases = sum(int(item.get("cases", 0)) for item in metrics)
    return {
        "suites": len(suite_results),
        "cases": total_cases,
        "recall_at_k": weighted_average(metrics, "recall_at_k"),
        "mrr_at_k": weighted_average(metrics, "mrr_at_k"),
        "hit_rate_at_k": weighted_average(metrics, "hit_rate_at_k"),
        "target_status": target_status(
            {
                "recall_at_k": weighted_average(metrics, "recall_at_k"),
                "mrr_at_k": weighted_average(metrics, "mrr_at_k"),
                "hit_rate_at_k": weighted_average(metrics, "hit_rate_at_k"),
            },
            RETRIEVAL_TARGETS,
        ),
    }


def evaluate_agent_suites(
    suites: list[dict],
    result_loader: Callable[[dict], list[dict]],
) -> list[dict]:
    suite_results = []
    for suite in suites:
        cases = _suite_cases(suite)
        result_records = result_loader(suite)
        metrics = evaluate_agent_cases(cases, result_records)
        suite_results.append(
            {
                "suite_id": suite.get("id", ""),
                "name": suite.get("name", ""),
                "risk_level": suite.get("risk_level", ""),
                "description": suite.get("description", ""),
                "confidence_note": confidence_note(metrics["cases"], str(suite.get("risk_level", ""))),
                "target_status": target_status(metrics, AGENT_TARGETS),
                "metrics": metrics,
            }
        )
    return suite_results


def evaluate_retrieval_suites(
    suites: list[dict],
    result_loader: Callable[[dict], list[dict]],
    k: int,
) -> list[dict]:
    suite_results = []
    for suite in suites:
        cases = _suite_cases(suite)
        result_records = result_loader(suite)
        metrics = evaluate_retrieval_cases(cases, result_records, k=k)
        suite_results.append(
            {
                "suite_id": suite.get("id", ""),
                "name": suite.get("name", ""),
                "risk_level": suite.get("risk_level", ""),
                "description": suite.get("description", ""),
                "confidence_note": confidence_note(metrics["cases"], str(suite.get("risk_level", ""))),
                "target_status": target_status(metrics, RETRIEVAL_TARGETS),
                "metrics": metrics,
            }
        )
    return suite_results


def _load_result_map(path: Path) -> dict[str, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("suites"), dict):
        return payload["suites"]
    raise ValueError("result map must be {'suites': {'suite_id': [records...]}}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-suite Career Agent and RAG evaluations")
    parser.add_argument("--agent-suites", type=Path, default=Path(__file__).with_name("agent_eval_suites.json"))
    parser.add_argument(
        "--retrieval-suites",
        type=Path,
        default=Path(__file__).with_name("retrieval_eval_suites.json"),
    )
    parser.add_argument("--agent-results", type=Path, help="Optional suite result map for Agent offline eval")
    parser.add_argument("--retrieval-results", type=Path, help="Optional suite result map for retrieval offline eval")
    parser.add_argument("--live-agent", action="store_true", help="Run the current Agent against all Agent suites")
    parser.add_argument(
        "--agent-tool-mode",
        choices=["fixture_tools", "live_tools"],
        default="fixture_tools",
        help="fixture_tools keeps tool outputs deterministic; live_tools calls the configured RAG/LLM tools",
    )
    parser.add_argument(
        "--agent-routing-modes",
        nargs="+",
        choices=["deterministic_first", "llm_autonomy"],
        default=["deterministic_first"],
        help="Run one or more Agent routing modes. llm_autonomy may call the configured LLM.",
    )
    parser.add_argument("--live-retrieval", action="store_true", help="Run the current retriever against all RAG suites")
    parser.add_argument(
        "--retrieval-mode",
        choices=["bm25_only", "hybrid_live"],
        default="bm25_only",
        help="bm25_only is stable and offline; hybrid_live calls the configured embedding/rerank stack",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("latest_multi_metrics.json"))
    args = parser.parse_args()

    agent_suites = load_suites(args.agent_suites)
    retrieval_suites = load_suites(args.retrieval_suites)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": {},
        "retrieval": {},
        "execution": {
            "agent_tool_mode": args.agent_tool_mode,
            "retrieval_mode": args.retrieval_mode,
            "retrieval_k": args.k,
        },
        "credibility_notes": [
            "不要只看 overall；应同时看 seed、directional、regression、robustness 各 suite。",
            "deterministic_first 评估规则路由和工具闭环，llm_autonomy 评估模型自主工具选择能力。",
            "当前 retrieval 标签为来源级标注，后续可升级为 chunk 级人工标注以提升可信度。",
        ],
    }

    if args.live_agent or args.agent_results:
        result_map = _load_result_map(args.agent_results) if args.agent_results else {}
        for routing_mode in args.agent_routing_modes:
            def load_agent_results(suite: dict, mode: str = routing_mode) -> list[dict]:
                if args.live_agent:
                    return run_agent_live(
                        _suite_cases(suite),
                        routing_mode=mode,
                        tool_mode=args.agent_tool_mode,
                    )
                return result_map.get(str(suite.get("id", "")), [])

            suite_results = evaluate_agent_suites(agent_suites, load_agent_results)
            report["agent"][routing_mode] = {
                "summary": summarize_agent_suites(suite_results),
                "suites": suite_results,
            }

    if args.live_retrieval or args.retrieval_results:
        result_map = _load_result_map(args.retrieval_results) if args.retrieval_results else {}

        def load_retrieval_results(suite: dict) -> list[dict]:
            if args.live_retrieval:
                return run_retrieval_live(
                    _suite_cases(suite),
                    k=args.k,
                    retrieval_mode=args.retrieval_mode,
                )
            return result_map.get(str(suite.get("id", "")), [])

        suite_results = evaluate_retrieval_suites(retrieval_suites, load_retrieval_results, k=args.k)
        report["retrieval"] = {
            "summary": summarize_retrieval_suites(suite_results),
            "suites": suite_results,
        }

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
