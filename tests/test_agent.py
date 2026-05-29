import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent import AgentResult, CareerAgent


def _make_llm_response(content=None, tool_calls=None):
    """构造模拟的 LLM 响应。"""
    return SimpleNamespace(
        content=content or "",
        tool_calls=tool_calls or [],
    )


def _make_tool_call(name: str, args: dict, call_id: str = "call_0"):
    """构造模拟的 tool_call 对象。"""
    return SimpleNamespace(name=name, args=args, id=call_id)


class AgentDirectAnswerTests(unittest.TestCase):
    """LLM 直接回答（不调用工具）的场景。"""

    def test_direct_answer(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_llm.invoke.return_value = _make_llm_response(content="你好！")

            result = agent.run("你好")

        self.assertTrue(result.success)
        self.assertEqual(result.answer, "你好！")
        self.assertEqual(len(result.steps), 0)

    def test_direct_answer_with_chinese(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_llm.invoke.return_value = _make_llm_response(
                content="当前有 3 个岗位。"
            )

            result = agent.run("有多少岗位？")

        self.assertTrue(result.success)
        self.assertIn("3", result.answer)


class AgentToolCallTests(unittest.TestCase):
    """工具调用场景。"""

    def test_single_tool_call(self):
        rag = MagicMock()
        store = MagicMock()
        store.list_job_postings.return_value = []
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            # 第一次调用：LLM 决定调用工具
            # 第二次调用：LLM 看到工具结果后直接回答
            mock_llm.invoke.side_effect = [
                _make_llm_response(tool_calls=[_make_tool_call("list_jobs", {})]),
                _make_llm_response(content="暂无岗位信息。"),
            ]

            result = agent.run("列出所有岗位")

        self.assertTrue(result.success)
        self.assertEqual(result.answer, "暂无岗位信息。")
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.steps[0].tool_name, "list_jobs")

    def test_multi_step_tool_calls(self):
        rag = MagicMock()
        store = MagicMock()
        store.list_job_postings.return_value = [
            SimpleNamespace(
                job_id="job_1",
                company="测试公司",
                title="AI 工程师",
                location="北京",
                raw_description="负责 AI 开发",
                required_skills=["Python"],
                preferred_skills=["PyTorch"],
            )
        ]
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            # 3 轮：list_jobs → get_job → 最终回答
            mock_llm.invoke.side_effect = [
                _make_llm_response(tool_calls=[_make_tool_call("list_jobs", {})]),
                _make_llm_response(
                    tool_calls=[
                        _make_tool_call("get_job", {"job_id": "job_1"}, "call_1")
                    ]
                ),
                _make_llm_response(content="测试公司正在招 AI 工程师。"),
            ]

            result = agent.run("看看有什么岗位，然后告诉我详情")

        self.assertTrue(result.success)
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(result.steps[0].tool_name, "list_jobs")
        self.assertEqual(result.steps[1].tool_name, "get_job")
        self.assertIn("测试公司", result.answer)

    def test_tool_output_truncated_in_steps(self):
        rag = MagicMock()
        store = MagicMock()
        store.list_job_postings.return_value = []
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            mock_llm.invoke.side_effect = [
                _make_llm_response(tool_calls=[_make_tool_call("list_jobs", {})]),
                _make_llm_response(content="无岗位"),
            ]

            result = agent.run("列出岗位")

        # tool_output 截断到 500 字符
        self.assertLessEqual(len(result.steps[0].tool_output), 500)


class AgentMaxIterationsTests(unittest.TestCase):
    """超过最大迭代次数。"""

    def test_max_iterations_exceeded(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            # LLM 始终返回工具调用，永不直接回答
            mock_llm.invoke.return_value = _make_llm_response(
                tool_calls=[_make_tool_call("list_jobs", {})]
            )

            result = agent.run("无限循环", max_iterations=3)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Max iterations exceeded")
        self.assertIn("步骤过多", result.answer)
        self.assertEqual(len(result.steps), 3)


class AgentErrorHandlingTests(unittest.TestCase):
    """错误处理场景。"""

    def test_llm_error(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_llm.invoke.side_effect = RuntimeError("API 连接失败")

            result = agent.run("测试")

        self.assertFalse(result.success)
        self.assertIn("API 连接失败", result.answer)
        self.assertIn("API 连接失败", result.error)

    def test_unknown_tool(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("nonexistent_tool", {})
        self.assertEqual(result, "未知工具: nonexistent_tool")

    def test_tool_execution_error(self):
        """工具内部异常被工具自身捕获，返回错误描述而非抛出。"""
        rag = MagicMock()
        store = MagicMock()
        store.list_job_postings.side_effect = RuntimeError("数据库错误")
        agent = CareerAgent(rag, store)

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            mock_llm.invoke.side_effect = [
                _make_llm_response(tool_calls=[_make_tool_call("list_jobs", {})]),
                _make_llm_response(content="工具报错了"),
            ]

            result = agent.run("列出岗位")

        self.assertTrue(result.success)
        # 工具内部捕获异常，返回包含错误信息的字符串
        self.assertIn("失败", result.steps[0].tool_output)


class AgentToolDispatchTests(unittest.TestCase):
    """验证工具正确分发到对应的底层函数。"""

    def test_list_jobs_dispatches(self):
        rag = MagicMock()
        store = MagicMock()
        store.list_job_postings.return_value = []
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("list_jobs", {})
        store.list_job_postings.assert_called_once()
        self.assertIn("暂无", result)

    def test_get_profile_dispatches(self):
        rag = MagicMock()
        store = MagicMock()
        store.load_candidate_profile.return_value = SimpleNamespace(
            name="张三", phone="13800000000", email="", city="",
            target_role="", preferred_locations="", homepage="", summary="",
        )
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("get_profile", {})
        store.load_candidate_profile.assert_called_once()
        self.assertIn("张三", result)

    def test_list_evidence_dispatches(self):
        rag = MagicMock()
        store = MagicMock()
        store.list_profile_evidence.return_value = []
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("list_evidence", {"category": ""})
        store.list_profile_evidence.assert_called_once()
        self.assertIn("暂无", result)

    def test_search_knowledge_dispatches(self):
        rag = MagicMock()
        rag.search.return_value = []
        store = MagicMock()
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("search_knowledge", {"query": "test", "top_k": 3})
        rag.search.assert_called_once_with("test", top_k=3)
        self.assertIn("未找到", result)

    def test_ask_knowledge_dispatches(self):
        rag = MagicMock()
        rag.ask.return_value = {"answer": "测试答案", "sources": []}
        store = MagicMock()
        agent = CareerAgent(rag, store)

        result = agent._execute_tool("ask_knowledge", {"question": "问题"})
        rag.ask.assert_called_once()
        self.assertIn("测试答案", result)


class AgentOpenaiToolsTests(unittest.TestCase):
    """验证 OpenAI 工具格式转换。"""

    def test_all_tools_converted(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        self.assertEqual(len(agent._openai_tools), 8)
        names = {t["function"]["name"] for t in agent._openai_tools}
        expected = {
            "search_knowledge", "ask_knowledge", "list_jobs", "get_job",
            "analyze_match", "list_evidence", "tailor_resume", "get_profile",
        }
        self.assertEqual(names, expected)

    def test_tool_map_matches_tools(self):
        rag = MagicMock()
        store = MagicMock()
        agent = CareerAgent(rag, store)

        self.assertEqual(set(agent.tool_map.keys()), {t.name for t in agent.tools})


if __name__ == "__main__":
    unittest.main()
