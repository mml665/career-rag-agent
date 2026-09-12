from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI

from tools import create_tools

if TYPE_CHECKING:
    from career_store import CareerStore
    from rag_agent import RagAssistant

SYSTEM_PROMPT = """你是一个智能求职助手，帮助用户管理求职流程、分析岗位匹配度、定制简历。

你可以使用以下工具：
- search_knowledge: 检索参考资料库（简历规范、公司资料等）
- ask_knowledge: 基于资料库回答问题
- list_jobs: 列出所有岗位
- get_job: 获取岗位详情
- analyze_match: 分析岗位匹配度
- list_evidence: 列出履历证据
- tailor_resume: 定制简历
- get_profile: 获取个人档案

工作原则：
1. 根据用户需求选择合适的工具
2. 复杂任务可以分步执行
3. 工具调用结果要准确反馈给用户
4. 如果信息不足，主动询问用户

回复格式：
- 直接回答用户问题，不要重复工具调用的过程
- 使用中文回复
- 结构化展示重要信息
"""


@dataclass
class AgentStep:
    """单步执行结果。"""
    tool_name: str
    tool_input: dict
    tool_output: str
    call_id: str = ""
    latency_ms: int = 0
    error_message: str = ""


@dataclass
class AgentResult:
    """Agent 执行结果。"""
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    success: bool = True
    error: str = ""
    run_id: str = ""


class CareerAgent:
    """智能求职 Agent，支持 Tool Calling。"""

    def __init__(
        self,
        rag_assistant: RagAssistant,
        career_store: CareerStore,
    ):
        self.rag_assistant = rag_assistant
        self.career_store = career_store
        self.tools = create_tools(rag_assistant, career_store)
        self.tool_map = {tool.name: tool for tool in self.tools}
        self._openai_tools = []
        for t in self.tools:
            try:
                self._openai_tools.append(convert_to_openai_tool(t))
            except Exception:
                pass  # 跳过无法转换的工具
        self._llm = None

    def _get_llm(self) -> ChatOpenAI:
        """获取 LLM 实例。"""
        if self._llm is None:
            from rag_agent import dashscope_api_key, dashscope_base_url, DEFAULT_CHAT_MODEL

            self._llm = ChatOpenAI(
                api_key=dashscope_api_key(),
                base_url=dashscope_base_url(),
                model=os.getenv("OPENAI_MODEL", DEFAULT_CHAT_MODEL),
                temperature=0,
            )
        return self._llm

    def run(
        self,
        user_input: str,
        max_iterations: int = 10,
        context: dict | None = None,
    ) -> AgentResult:
        """执行用户请求，支持多步工具调用。"""
        run_id = f"run_{uuid4().hex[:12]}"
        started_at = perf_counter()
        run_context = context or {}
        steps = []
        memory_context = self._load_memory_context()
        memory_snapshot = self._memory_snapshot()
        if not run_context.get("disable_deterministic_policy"):
            deterministic = self._run_deterministic_policy(
                user_input,
                run_id,
                started_at,
                run_context,
                memory_snapshot,
            )
            if deterministic is not None:
                return deterministic
        messages = [
            SystemMessage(content=self._build_system_prompt(memory_context)),
            HumanMessage(content=user_input),
        ]

        for _ in range(max_iterations):
            try:
                response = self._get_llm().invoke(messages, tools=self._openai_tools)
            except Exception as e:
                result = AgentResult(
                    answer=f"调用 LLM 失败: {str(e)}",
                    steps=steps,
                    success=False,
                    error=str(e),
                    run_id=run_id,
                )
                self._finalize_run(
                    run_id,
                    user_input,
                    result,
                    started_at,
                    run_context,
                    memory_snapshot,
                )
                return result

            if not response.tool_calls:
                result = AgentResult(
                    answer=response.content or "抱歉，我无法处理这个请求。",
                    steps=steps,
                    run_id=run_id,
                )
                self._finalize_run(
                    run_id,
                    user_input,
                    result,
                    started_at,
                    run_context,
                    memory_snapshot,
                )
                return result

            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = self._tool_call_field(tool_call, "name", "")
                tool_args = self._tool_call_field(tool_call, "args", {}) or {}
                tool_call_id = self._tool_call_field(tool_call, "id", tool_name)

                tool_started_at = perf_counter()
                tool_result = self._execute_tool(tool_name, tool_args)
                tool_latency_ms = int((perf_counter() - tool_started_at) * 1000)
                error_message = self._tool_error_message(tool_result)

                steps.append(AgentStep(
                    tool_name=tool_name,
                    tool_input=tool_args,
                    tool_output=tool_result[:500],
                    call_id=tool_call_id,
                    latency_ms=tool_latency_ms,
                    error_message=error_message,
                ))

                messages.append(ToolMessage(
                    content=tool_result,
                    tool_call_id=tool_call_id,
                ))

        result = AgentResult(
            answer="任务执行步骤过多，请尝试简化请求。",
            steps=steps,
            success=False,
            error="Max iterations exceeded",
            run_id=run_id,
        )
        self._finalize_run(
            run_id,
            user_input,
            result,
            started_at,
            run_context,
            memory_snapshot,
        )
        return result

    @staticmethod
    def _tool_call_field(tool_call: object, name: str, default=None):
        if isinstance(tool_call, dict):
            return tool_call.get(name, default)
        return getattr(tool_call, name, default)

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行单个工具调用。"""
        tool = self.tool_map.get(tool_name)
        if not tool:
            return f"未知工具: {tool_name}"

        try:
            result = tool.invoke(tool_args)
            return str(result)
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    def _run_deterministic_policy(
        self,
        user_input: str,
        run_id: str,
        started_at: float,
        context: dict,
        memory_snapshot: list[dict],
    ) -> AgentResult | None:
        plan = self._deterministic_plan(user_input)
        if not plan:
            return None

        steps: list[AgentStep] = []
        outputs = []
        for tool_name, tool_args in plan:
            tool_started_at = perf_counter()
            tool_result = self._execute_tool(tool_name, tool_args)
            tool_latency_ms = int((perf_counter() - tool_started_at) * 1000)
            steps.append(
                AgentStep(
                    tool_name=tool_name,
                    tool_input=tool_args,
                    tool_output=tool_result[:500],
                    call_id=f"call_{uuid4().hex[:12]}",
                    latency_ms=tool_latency_ms,
                    error_message=self._tool_error_message(tool_result),
                )
            )
            outputs.append(tool_result)

        step_errors = [step.error_message for step in steps if step.error_message]
        answer = self._render_deterministic_answer(user_input, plan, outputs)
        result = AgentResult(
            answer=answer,
            steps=steps,
            success=not step_errors,
            error="; ".join(step_errors),
            run_id=run_id,
        )
        self._finalize_run(
            run_id,
            user_input,
            result,
            started_at,
            context,
            memory_snapshot,
        )
        return result

    def _deterministic_plan(self, user_input: str) -> list[tuple[str, dict]] | None:
        text = user_input.strip()
        if not text:
            return None

        job_id = self._extract_job_id(text)
        negates_tailoring = re.search(r"(不要|不用|无需|先别|别).{0,6}定制", text) is not None
        if job_id and ("匹配" in text or "分析" in text) and ("只" in text or negates_tailoring):
            return [("analyze_match", {"job_id": job_id})]

        if (
            "定制" in text
            and not negates_tailoring
            and any(marker in text for marker in ("简历", "履历", "项目经历"))
        ):
            if not job_id:
                return None
            category = "project" if "项目" in text else "skill" if "技能" in text else "project"
            return [
                ("get_job", {"job_id": job_id}),
                ("list_evidence", {"category": ""}),
                ("tailor_resume", {"job_id": job_id, "category": category}),
            ]

        if job_id and ("匹配" in text or "分析" in text):
            return [("analyze_match", {"job_id": job_id})]

        if job_id and any(marker in text for marker in ("详情", "岗位信息", "JD", "jd", "描述")):
            return [("get_job", {"job_id": job_id})]

        if "履历证据" in text or "已确认履历" in text:
            category = "project" if "项目" in text else "skill" if "技能" in text else ""
            return [("list_evidence", {"category": category})]

        if "个人档案" in text or "求职方向" in text:
            return [("get_profile", {})]

        if "岗位" in text and any(marker in text for marker in ("列出", "保存", "现在", "有哪些")):
            return [("list_jobs", {})]

        knowledge_markers = ("怎么", "如何", "为什么", "区别", "建议", "规范", "技巧", "哪些", "什么")
        knowledge_domains = ("简历", "面试", "RAG", "Agent", "公司研究")
        if any(marker in text for marker in knowledge_markers) and any(
            domain in text for domain in knowledge_domains
        ):
            return [("ask_knowledge", {"question": text, "top_k": 4})]

        return None

    @staticmethod
    def _extract_job_id(text: str) -> str:
        match = re.search(r"\bjob_[A-Za-z0-9_-]+\b", text)
        return match.group(0) if match else ""

    @staticmethod
    def _render_deterministic_answer(
        user_input: str,
        plan: list[tuple[str, dict]],
        outputs: list[str],
    ) -> str:
        tool_names = [tool_name for tool_name, _ in plan]
        last_output = outputs[-1] if outputs else ""
        if tool_names == ["list_jobs"]:
            return f"岗位列表如下：\n{last_output}"
        if tool_names == ["get_profile"]:
            return f"求职方向与个人档案如下：\n{last_output}"
        if tool_names == ["analyze_match"]:
            return f"匹配分析结果如下：\n{last_output}"
        if tool_names == ["ask_knowledge"]:
            return f"项目/求职参考建议如下：\n{last_output}"
        if tool_names == ["get_job", "list_evidence", "tailor_resume"]:
            return f"项目经历定制结果如下：\n{last_output}"
        return f"已按请求处理：{user_input}\n{last_output}"

    def _build_system_prompt(self, memory_context: str) -> str:
        if not memory_context:
            return SYSTEM_PROMPT
        return (
            f"{SYSTEM_PROMPT}\n\n"
            "以下是用户已确认或明确表达过的长期记忆。只在相关时使用，不要编造或覆盖：\n"
            f"{memory_context}"
        )

    def _load_memory_context(self) -> str:
        try:
            memory_context = self.career_store.build_agent_memory_context(limit=8)
        except Exception:
            return ""
        return memory_context if isinstance(memory_context, str) else ""

    def _memory_snapshot(self) -> list[dict]:
        try:
            memories = self.career_store.list_agent_memories(limit=8)
        except Exception:
            return []
        snapshot = []
        for item in memories:
            if isinstance(item, dict):
                snapshot.append(item)
            else:
                snapshot.append(
                    {
                        "memory_id": getattr(item, "memory_id", ""),
                        "memory_type": getattr(item, "memory_type", ""),
                        "content": getattr(item, "content", ""),
                    }
                )
        return snapshot

    def _finalize_run(
        self,
        run_id: str,
        user_input: str,
        result: AgentResult,
        started_at: float,
        context: dict,
        memory_snapshot: list[dict],
    ) -> None:
        latency_ms = int((perf_counter() - started_at) * 1000)
        try:
            self.career_store.record_agent_run(
                run_id=run_id,
                user_message=user_input,
                final_answer=result.answer,
                success=result.success,
                error=result.error,
                tool_call_count=len(result.steps),
                latency_ms=latency_ms,
                model=self._model_name(),
                context=context,
                memory_snapshot=memory_snapshot,
            )
            for step in result.steps:
                self.career_store.record_agent_tool_call(
                    call_id=step.call_id or f"call_{uuid4().hex[:12]}",
                    run_id=run_id,
                    tool_name=step.tool_name,
                    tool_input=step.tool_input,
                    tool_output=step.tool_output,
                    latency_ms=step.latency_ms,
                    error_message=step.error_message,
                )
            for memory_type, content in self._extract_memory_candidates(user_input):
                self.career_store.remember_agent_memory(
                    memory_type=memory_type,
                    content=content,
                    source=f"agent_run:{run_id}",
                    confidence=1.0,
                )
        except Exception:
            # 审计和记忆失败不应影响用户主流程。
            return

    @staticmethod
    def _tool_error_message(tool_result: str) -> str:
        failure_prefixes = (
            "未知工具",
            "工具执行失败",
            "检索失败",
            "问答失败",
            "获取岗位列表失败",
            "获取岗位信息失败",
            "未找到岗位",
            "分析匹配度失败",
            "获取履历证据失败",
            "定制简历失败",
            "获取个人档案失败",
        )
        if tool_result.startswith(failure_prefixes):
            return tool_result
        return ""

    @staticmethod
    def _extract_memory_candidates(user_input: str) -> list[tuple[str, str]]:
        text = user_input.strip()
        if not text:
            return []

        candidates: list[tuple[str, str]] = []
        remember_markers = ("记住", "帮我记住", "请记住")
        if any(marker in text for marker in remember_markers):
            content = text
            for marker in remember_markers:
                content = content.replace(marker, "")
            content = content.lstrip("：:，, ").strip()
            if content:
                candidates.append(("preference", content[:300]))

        goal_markers = ("我的求职目标是", "我的目标岗位是", "我主要想找")
        for marker in goal_markers:
            if marker in text:
                content = text.split(marker, 1)[1].strip("：:，, 。")
                if content:
                    candidates.append(("goal", content[:300]))
                break

        constraint_markers = ("我不考虑", "不要推荐", "不想投")
        for marker in constraint_markers:
            if marker in text:
                content = text.split(marker, 1)[1].strip("：:，, 。")
                if content:
                    candidates.append(("constraint", content[:300]))
                break

        deduped: list[tuple[str, str]] = []
        seen = set()
        for item in candidates:
            key = (item[0], item[1].casefold())
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    @staticmethod
    def _model_name() -> str:
        from rag_agent import DEFAULT_CHAT_MODEL

        return os.getenv("OPENAI_MODEL", DEFAULT_CHAT_MODEL)
