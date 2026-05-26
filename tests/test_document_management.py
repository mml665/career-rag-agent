import tempfile
import unittest
from pathlib import Path

from rag_agent import RagAssistant, RagConfig


class DocumentManagementTests(unittest.TestCase):
    def build_assistant(self, root: Path) -> RagAssistant:
        return RagAssistant(
            RagConfig(
                docs_dir=root / "documents",
                upload_dir=root / "uploads",
                chroma_dir=root / "chroma",
                history_path=root / "history.jsonl",
            )
        )

    def test_delete_document_removes_managed_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            uploaded = assistant.save_upload("notes.md", b"# Notes")

            self.assertTrue(assistant.delete_document(uploaded))
            self.assertFalse(uploaded.exists())

    def test_delete_document_rejects_file_outside_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assistant = self.build_assistant(root / "library")
            outside = root / "private.txt"
            outside.write_text("keep", encoding="utf-8")

            with self.assertRaises(ValueError):
                assistant.delete_document(outside)
            self.assertTrue(outside.exists())

    def test_clear_uploads_keeps_documents_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant.save_upload("one.txt", b"one")
            assistant.save_upload("two.md", b"two")
            stored_document = assistant.config.docs_dir / "reference.md"
            stored_document.write_text("reference", encoding="utf-8")

            self.assertEqual(assistant.clear_uploads(), 2)
            self.assertTrue(stored_document.exists())
            self.assertEqual(assistant.list_documents(), [stored_document])


if __name__ == "__main__":
    unittest.main()
