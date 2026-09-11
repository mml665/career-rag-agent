import unittest

from evals.retrieval_eval import evaluate_cases


class RetrievalEvaluationTests(unittest.TestCase):
    def test_recall_and_mrr_are_calculated(self):
        golden = [
            {"id": "a", "query": "q1", "relevant_sources": ["docs/a.md"]},
            {"id": "b", "query": "q2", "relevant_sources": ["docs/b.md", "docs/c.md"]},
        ]
        results = [
            {"case_id": "a", "results": [{"source": "docs/no.md"}, {"source": "docs/a.md"}]},
            {"case_id": "b", "results": [{"source": "docs/c.md"}]},
        ]

        metrics = evaluate_cases(golden, results, k=2)

        self.assertEqual(metrics["cases"], 2)
        self.assertEqual(metrics["recall_at_k"], 0.75)
        self.assertEqual(metrics["mrr_at_k"], 0.75)
        self.assertEqual(metrics["hit_rate_at_k"], 1.0)

    def test_source_paths_are_normalised(self):
        golden = [{"id": "a", "query": "q", "relevant_sources": ["简历写作规范.md"]}]
        results = [{"case_id": "a", "results": [{"source": "E:/project/documents/简历写作规范.md"}]}]

        metrics = evaluate_cases(golden, results, k=1)

        self.assertEqual(metrics["recall_at_k"], 1.0)

    def test_missing_results_are_counted_as_misses(self):
        golden = [{"id": "a", "query": "q", "relevant_sources": ["a.md"]}]

        metrics = evaluate_cases(golden, [], k=5)

        self.assertEqual(metrics["recall_at_k"], 0.0)
        self.assertEqual(metrics["mrr_at_k"], 0.0)
        self.assertEqual(metrics["hit_rate_at_k"], 0.0)


if __name__ == "__main__":
    unittest.main()

