from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Iterable


def _step_tool_name(step: object) -> str:
    if isinstance(step, str):
        return step
    if isinstance(step, dict):
        return str(step.get("tool_name") or step.get("name") or "")
    return str(getattr(step, "tool_name", ""))


def _step_error(step: object) -> str:
    if isinstance(step, dict):
        return str(step.get("error_message") or step.get("error") or "")
    return str(getattr(step, "error_message", ""))


def _normalise_results(result_records: Iterable[dict]) -> dict[str, dict]:
    records = {}
    for item in result_records:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or item.get("id") or "")
        if case_id:
            records[case_id] = item
    return records


def _ordered_subsequence(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    cursor = 0
    for tool in actual:
        if tool == expected[cursor]:
            cursor += 1
            if cursor == len(expected):
                return True
    return False


def _tool_metrics(required_tools: list[str], actual_tools: list[str]) -> tuple[float, float]:
    required = set(required_tools)
    actual = set(actual_tools)
    if not required and not actual:
        return 1.0, 1.0
    precision = 1.0 if not actual else len(required & actual) / len(actual)
    recall = 1.0 if not required else len(required & actual) / len(required)
    return precision, recall


def evaluate_agent_cases(
    golden_cases: Iterable[dict],
    result_records: Iterable[dict],
) -> dict:
    """Evaluate Agent task completion, tool choice and answer constraints.

    Golden cases can define these fields:
    - id, user_input
    - required_tools: tools that must appear at least once
    - expected_tool_sequence: ordered subsequence expected in the trajectory
    - forbidden_tools: tools that should not be called
    - required_answer_terms / forbidden_answer_terms
    - expect_success, max_tool_calls, allow_tool_errors
    """
    cases = list(golden_cases)
    results_by_id = _normalise_results(result_records)
    details = []

    for case in cases:
        case_id = str(case.get("id", ""))
        result = results_by_id.get(case_id, {})
        steps = result.get("steps", []) if isinstance(result, dict) else []
        actual_tools = [_step_tool_name(step) for step in steps if _step_tool_name(step)]
        required_tools = list(case.get("required_tools") or case.get("expected_tools") or [])
        expected_sequence = list(case.get("expected_tool_sequence") or [])
        forbidden_tools = set(case.get("forbidden_tools") or [])
        answer = str(result.get("answer", ""))
        final_error = str(result.get("error", ""))

        tool_precision, tool_recall = _tool_metrics(required_tools, actual_tools)
        forbidden_tool_hit = any(tool in forbidden_tools for tool in actual_tools)
        required_tool_ok = set(required_tools).issubset(set(actual_tools))
        sequence_ok = _ordered_subsequence(expected_sequence, actual_tools)
        tool_path_ok = required_tool_ok and sequence_ok and not forbidden_tool_hit

        required_terms = [str(term) for term in case.get("required_answer_terms", [])]
        forbidden_terms = [str(term) for term in case.get("forbidden_answer_terms", [])]
        answer_required_ok = all(term in answer for term in required_terms)
        answer_forbidden_ok = not any(term in answer for term in forbidden_terms)
        answer_ok = answer_required_ok and answer_forbidden_ok

        expect_success = bool(case.get("expect_success", True))
        success_ok = bool(result.get("success", False)) == expect_success
        max_tool_calls = case.get("max_tool_calls")
        tool_count_ok = max_tool_calls is None or len(actual_tools) <= int(max_tool_calls)
        allow_tool_errors = bool(case.get("allow_tool_errors", False))
        step_errors = [_step_error(step) for step in steps if _step_error(step)]
        errors_ok = allow_tool_errors or not step_errors
        pass_case = success_ok and tool_path_ok and answer_ok and tool_count_ok and errors_ok
        failure_reasons = []
        if not success_ok:
            failure_reasons.append("success_state_mismatch")
        if not tool_path_ok:
            failure_reasons.append("tool_path_mismatch")
        if not answer_ok:
            failure_reasons.append("answer_rule_failed")
        if not tool_count_ok:
            failure_reasons.append("too_many_tool_calls")
        if not errors_ok:
            failure_reasons.append("tool_error")
        if final_error and not allow_tool_errors:
            failure_reasons.append("final_error")

        details.append(
            {
                "case_id": case_id,
                "user_input": case.get("user_input", ""),
                "pass": pass_case,
                "success_ok": success_ok,
                "tool_path_ok": tool_path_ok,
                "answer_ok": answer_ok,
                "tool_count_ok": tool_count_ok,
                "errors_ok": errors_ok,
                "tool_precision": round(tool_precision, 4),
                "tool_recall": round(tool_recall, 4),
                "expected_tool_sequence": expected_sequence,
                "required_tools": required_tools,
                "actual_tools": actual_tools,
                "step_errors": step_errors,
                "final_error": final_error,
                "failure_reasons": failure_reasons,
            }
        )

    total = len(details)
    if total == 0:
        return {
            "cases": 0,
            "pass_rate": 0.0,
            "success_accuracy": 0.0,
            "tool_path_accuracy": 0.0,
            "answer_rule_pass_rate": 0.0,
            "tool_precision": 0.0,
            "tool_recall": 0.0,
            "avg_tool_calls": 0.0,
            "details": [],
        }

    return {
        "cases": total,
        "pass_rate": round(sum(item["pass"] for item in details) / total, 4),
        "success_accuracy": round(sum(item["success_ok"] for item in details) / total, 4),
        "tool_path_accuracy": round(sum(item["tool_path_ok"] for item in details) / total, 4),
        "answer_rule_pass_rate": round(sum(item["answer_ok"] for item in details) / total, 4),
        "tool_precision": round(sum(item["tool_precision"] for item in details) / total, 4),
        "tool_recall": round(sum(item["tool_recall"] for item in details) / total, 4),
        "avg_tool_calls": round(sum(len(item["actual_tools"]) for item in details) / total, 4),
        "details": details,
    }


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_rag_assistant():
    from rag_agent import ResumeTailoringResult

    class FixtureRagAssistant:
        def search(self, question: str, top_k: int | None = None) -> list[dict]:
            return [
                {
                    "source": "fixture://career-knowledge",
                    "content": f"与问题相关的评测资料：{question}",
                    "score": 0.91,
                }
            ][: top_k or 1]

        def ask(self, question: str, top_k: int | None = None) -> dict:
            return {
                "question": question,
                "answer": (
                    "可以围绕项目背景、Agent 工具调用、RAG 检索、公司研究、"
                    f"简历证据和面试表达来回答：{question}"
                ),
                "sources": [{"source": "fixture://career-knowledge"}],
            }

        def tailor_resume(
            self,
            job_description: str,
            evidence: list[str],
            current_text: str = "",
            request: str = "",
        ) -> ResumeTailoringResult:
            return ResumeTailoringResult(
                fit_assessment="岗位与已确认履历中的 FastAPI、RAG、Agent 项目经验匹配。",
                recommended_text="基于已确认项目证据，负责 FastAPI 接口、RAG 检索和 Agent 工具调用闭环。",
                evidence_basis="; ".join(evidence[:3]),
                gap_notes="不要编造未验证经历，缺口应单独说明。",
            )

    return FixtureRagAssistant()


def _run_live(
    golden_cases: list[dict],
    routing_mode: str = "deterministic_first",
    tool_mode: str = "live_tools",
) -> list[dict]:
    from agent import CareerAgent
    from career_store import CareerStore
    from rag_agent import RagAssistant

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CareerStore(Path(temp_dir) / "career")
        store.save_candidate_profile(
            name="评测候选人",
            city="上海",
            target_role="AI Agent 应用开发实习生",
            summary="关注 RAG、Tool Calling、FastAPI 与前端工程化。",
        )
        store.add_profile_evidence(
            category="project",
            content="使用 FastAPI、Vue3、Chroma、BM25、RRF 和 LangChain Tool Calling 实现求职 Agent。",
        )
        store.add_profile_evidence(
            category="skill",
            content="熟悉 Python、FastAPI、RAG、向量检索、BM25、Rerank 和自动化测试。",
        )
        job = store.add_job_posting(
            company="评测科技",
            title="AI Agent 开发实习生",
            location="上海",
            raw_description="负责 RAG 应用、Agent 工具调用、FastAPI 接口和前端页面开发。",
            required_skills=["RAG", "FastAPI", "Agent"],
            preferred_skills=["Vue3", "BM25", "Rerank"],
        )
        rag_assistant = _fixture_rag_assistant() if tool_mode == "fixture_tools" else RagAssistant()
        agent = CareerAgent(rag_assistant, store)
        records = []
        for case in golden_cases:
            user_input = str(case.get("user_input") or case.get("query") or "")
            user_input = user_input.replace("job_123", job.job_id)
            context = {"eval_case_id": case.get("id", ""), "routing_mode": routing_mode}
            if routing_mode == "llm_autonomy":
                context["disable_deterministic_policy"] = True
            result = agent.run(
                user_input,
                max_iterations=int(case.get("max_iterations", 8)),
                context=context,
            )
            records.append(
                {
                    "case_id": case.get("id", ""),
                    "answer": result.answer,
                    "success": result.success,
                    "error": result.error,
                    "routing_mode": routing_mode,
                    "tool_mode": tool_mode,
                    "steps": [
                        {
                            "tool_name": step.tool_name,
                            "tool_input": step.tool_input,
                            "error_message": step.error_message,
                        }
                        for step in result.steps
                    ],
                }
            )
        return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Career Agent behaviour")
    parser.add_argument("--golden", type=Path, default=Path(__file__).with_name("agent_golden_set.json"))
    parser.add_argument("--results", type=Path, help="JSON file containing case_id/answer/success/steps records")
    parser.add_argument("--live", action="store_true", help="Run the current Agent against golden cases")
    parser.add_argument(
        "--routing-mode",
        choices=["deterministic_first", "llm_autonomy"],
        default="deterministic_first",
        help="deterministic_first uses the rule router before LLM fallback; llm_autonomy disables that router",
    )
    parser.add_argument(
        "--tool-mode",
        choices=["live_tools", "fixture_tools"],
        default="live_tools",
        help="fixture_tools replaces LLM-backed knowledge/tailoring tools with stable fixtures for CI",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    golden_payload = _load_json(args.golden)
    golden_cases = golden_payload.get("cases", []) if isinstance(golden_payload, dict) else golden_payload
    if args.live:
        result_records = _run_live(golden_cases, routing_mode=args.routing_mode, tool_mode=args.tool_mode)
    elif args.results:
        result_payload = _load_json(args.results)
        result_records = result_payload.get("results", []) if isinstance(result_payload, dict) else result_payload
    else:
        parser.error("provide --results or --live")

    metrics = evaluate_agent_cases(golden_cases, result_records)
    rendered = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
