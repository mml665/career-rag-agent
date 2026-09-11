import unittest

from evals.match_feedback_eval import summarize_feedback


class MatchFeedbackEvaluationTests(unittest.TestCase):
    def test_feedback_summary_tracks_accuracy_and_actionable_cases(self):
        summary = summarize_feedback(
            [
                {
                    "feedback_id": "f1",
                    "analysis_id": "a1",
                    "rating": "accurate",
                    "issue_type": "",
                    "comment": "准确",
                },
                {
                    "feedback_id": "f2",
                    "analysis_id": "a2",
                    "rating": "wrong",
                    "issue_type": "hallucination",
                    "comment": "把未证实技能写成已掌握。",
                    "correction": "放入缺口提示。",
                },
            ]
        )

        self.assertEqual(summary["feedback_count"], 2)
        self.assertEqual(summary["accuracy_proxy"], 0.5)
        self.assertEqual(summary["issue_distribution"]["hallucination"], 1)
        self.assertEqual(summary["actionable_cases"][0]["feedback_id"], "f2")

    def test_empty_feedback_has_zero_metrics(self):
        summary = summarize_feedback([])

        self.assertEqual(summary["feedback_count"], 0)
        self.assertEqual(summary["accuracy_proxy"], 0.0)
        self.assertEqual(summary["actionable_cases"], [])


if __name__ == "__main__":
    unittest.main()
