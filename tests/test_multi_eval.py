import unittest

from evals.multi_eval import (
    confidence_note,
    evaluate_agent_suites,
    evaluate_retrieval_suites,
    summarize_agent_suites,
    summarize_retrieval_suites,
)


class MultiEvaluationTests(unittest.TestCase):
    def test_agent_suites_are_evaluated_separately_and_summarized(self):
        suites = [
            {
                "id": "core",
                "name": "核心",
                "risk_level": "seed",
                "cases": [{"id": "a", "required_tools": ["list_jobs"]}],
            },
            {
                "id": "robust",
                "name": "鲁棒",
                "risk_level": "robustness",
                "cases": [{"id": "b", "required_tools": ["get_profile"]}],
            },
        ]

        def load_results(suite):
            if suite["id"] == "core":
                return [{"case_id": "a", "success": True, "steps": [{"tool_name": "list_jobs"}]}]
            return [{"case_id": "b", "success": True, "steps": [{"tool_name": "list_jobs"}]}]

        results = evaluate_agent_suites(suites, load_results)
        summary = summarize_agent_suites(results)

        self.assertEqual(len(results), 2)
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertFalse(results[1]["target_status"]["tool_recall"]["met"])

    def test_retrieval_suites_are_weighted_by_case_count(self):
        suites = [
            {
                "id": "a",
                "risk_level": "seed",
                "cases": [{"id": "a1", "query": "q", "relevant_sources": ["a.md"]}],
            },
            {
                "id": "b",
                "risk_level": "directional",
                "cases": [
                    {"id": "b1", "query": "q", "relevant_sources": ["b.md"]},
                    {"id": "b2", "query": "q", "relevant_sources": ["c.md"]},
                ],
            },
        ]

        def load_results(suite):
            if suite["id"] == "a":
                return [{"case_id": "a1", "results": [{"source": "a.md"}]}]
            return [
                {"case_id": "b1", "results": [{"source": "no.md"}]},
                {"case_id": "b2", "results": [{"source": "c.md"}]},
            ]

        results = evaluate_retrieval_suites(suites, load_results, k=1)
        summary = summarize_retrieval_suites(results)

        self.assertEqual(summary["cases"], 3)
        self.assertEqual(summary["recall_at_k"], 0.6667)
        self.assertIn("small sample", confidence_note(3, "seed"))


if __name__ == "__main__":
    unittest.main()
