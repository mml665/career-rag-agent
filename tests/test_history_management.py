import json
import tempfile
import unittest
from pathlib import Path

from rag_agent import RagAssistant, RagConfig


class HistoryManagementTests(unittest.TestCase):
    def build_assistant(self, root: Path) -> RagAssistant:
        return RagAssistant(
            RagConfig(
                docs_dir=root / "documents",
                upload_dir=root / "uploads",
                chroma_dir=root / "chroma",
                history_path=root / "history.jsonl",
            )
        )

    def test_existing_history_receives_ids_and_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant.config.history_path.write_text(
                json.dumps(
                    {"time": "2026-05-26T10:00:00", "question": "总结资料库", "answer": "摘要"}
                )
                + "\n",
                encoding="utf-8",
            )

            history = assistant.load_history()

            self.assertTrue(history[0]["history_id"].startswith("history_"))
            self.assertTrue(assistant.delete_history_record(history[0]["history_id"]))
            self.assertEqual(assistant.load_history(), [])

    def test_clear_history_removes_all_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant._append_history({"time": "1", "question": "问题", "answer": "回答"})
            assistant._append_history({"time": "2", "question": "总结资料库", "answer": "摘要"})

            self.assertEqual(assistant.clear_history(), 2)
            self.assertEqual(assistant.load_history(), [])


if __name__ == "__main__":
    unittest.main()
