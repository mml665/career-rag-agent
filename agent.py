from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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


@dataclass
class AgentResult:
    """Agent 执行结果。"""
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    success: bool = True
    error: str = ""


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
        self._openai_tools = [convert_to_openai_tool(t) for t in self.tools]
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

    def run(self, user_input: str, max_iterations: int = 10) -> AgentResult:
        """执行用户请求，支持多步工具调用。"""
        steps = []
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_input),
        ]

        for _ in range(max_iterations):
            try:
                response = self._get_llm().invoke(messages, tools=self._openai_tools)
            except Exception as e:
                return AgentResult(
                    answer=f"调用 LLM 失败: {str(e)}",
                    steps=steps,
                    success=False,
                    error=str(e),
                )

            if not response.tool_calls:
                return AgentResult(answer=response.content, steps=steps)

            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.args

                tool_result = self._execute_tool(tool_name, tool_args)

                steps.append(AgentStep(
                    tool_name=tool_name,
                    tool_input=tool_args,
                    tool_output=tool_result[:500],
                ))

                messages.append(ToolMessage(
                    content=tool_result,
                    tool_call_id=tool_call.id,
                ))

        return AgentResult(
            answer="任务执行步骤过多，请尝试简化请求。",
            steps=steps,
            success=False,
            error="Max iterations exceeded",
        )

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
