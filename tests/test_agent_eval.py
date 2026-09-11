import unittest

from evals.agent_eval import evaluate_agent_cases


class AgentEvaluationTests(unittest.TestCase):
    def test_agent_eval_scores_success_tools_and_answer_rules(self):
        golden = [
            {
                "id": "case_ok",
                "user_input": "列出岗位",
                "required_tools": ["list_jobs"],
                "expected_tool_sequence": ["list_jobs"],
                "required_answer_terms": ["岗位"],
                "expect_success": True,
                "max_tool_calls": 1,
            },
            {
                "id": "case_bad",
                "user_input": "定制简历",
                "required_tools": ["get_job", "list_evidence", "tailor_resume"],
                "expected_tool_sequence": ["get_job", "list_evidence", "tailor_resume"],
                "forbidden_tools": ["search_knowledge"],
                "forbidden_answer_terms": ["编造"],
                "expect_success": True,
                "max_tool_calls": 4,
            },
        ]
        results = [
            {
                "case_id": "case_ok",
                "answer": "当前有 2 个岗位。",
                "success": True,
                "steps": [{"tool_name": "list_jobs"}],
            },
            {
                "case_id": "case_bad",
                "answer": "我会编造一段经历。",
                "success": True,
                "steps": [
                    {"tool_name": "get_job"},
                    {"tool_name": "search_knowledge"},
                    {"tool_name": "tailor_resume"},
                ],
            },
        ]

        metrics = evaluate_agent_cases(golden, results)

        self.assertEqual(metrics["cases"], 2)
        self.assertEqual(metrics["pass_rate"], 0.5)
        self.assertEqual(metrics["success_accuracy"], 1.0)
        self.assertEqual(metrics["answer_rule_pass_rate"], 0.5)
        self.assertEqual(metrics["details"][0]["actual_tools"], ["list_jobs"])
        self.assertFalse(metrics["details"][1]["tool_path_ok"])

    def test_agent_eval_accepts_string_steps_and_empty_cases(self):
        metrics = evaluate_agent_cases(
            [{"id": "case", "required_tools": ["get_profile"]}],
            [{"case_id": "case", "answer": "", "success": True, "steps": ["get_profile"]}],
        )

        self.assertEqual(metrics["tool_recall"], 1.0)
        self.assertEqual(evaluate_agent_cases([], [])["cases"], 0)

    def test_agent_eval_fails_cases_with_unexpected_tool_errors(self):
        metrics = evaluate_agent_cases(
            [{"id": "case", "required_tools": ["list_jobs"], "expect_success": True}],
            [
                {
                    "case_id": "case",
                    "answer": "工具失败。",
                    "success": True,
                    "steps": [{"tool_name": "list_jobs", "error_message": "工具执行失败"}],
                }
            ],
        )

        self.assertEqual(metrics["pass_rate"], 0.0)
        self.assertFalse(metrics["details"][0]["errors_ok"])


if __name__ == "__main__":
    unittest.main()
