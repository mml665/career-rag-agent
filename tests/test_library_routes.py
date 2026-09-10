import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from api.routes.library import list_documents, upload
from rag_agent import RagAssistant, RagConfig


class LibraryRouteTests(unittest.TestCase):
    def test_list_documents_returns_frontend_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "documents"
            uploads_dir = root / "uploads"
            docs_dir.mkdir()
            uploads_dir.mkdir()
            doc = docs_dir / "简历写作规范.md"
            doc.write_text("content", encoding="utf-8")

            assistant = RagAssistant(
                RagConfig(
                    docs_dir=docs_dir,
                    upload_dir=uploads_dir,
                    chroma_dir=root / "chroma",
                    history_path=root / "history.jsonl",
                )
            )

            result = list_documents(assistant)

            self.assertEqual(result[0]["name"], "简历写作规范.md")
            self.assertEqual(result[0]["size"], len("content"))
            self.assertTrue(result[0]["path"].endswith("简历写作规范.md"))

    def test_upload_returns_document_inspection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assistant = RagAssistant(
                RagConfig(
                    docs_dir=root / "documents",
                    upload_dir=root / "uploads",
                    chroma_dir=root / "chroma",
                    history_path=root / "history.jsonl",
                )
            )
            file = MagicMock()
            file.filename = "notes.md"
            file.read = AsyncMock(return_value=b"# Title\n\ncontent")

            import asyncio

            result = asyncio.run(upload(file, assistant))

            self.assertTrue(result["ok"])
            self.assertEqual(result["inspection"]["document_type"], "structured_text")
            self.assertEqual(result["inspection"]["parser_strategy"], "heading_aware_text")


if __name__ == "__main__":
    unittest.main()
