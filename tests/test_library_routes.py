import tempfile
import unittest
from pathlib import Path

from api.routes.library import list_documents
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


if __name__ == "__main__":
    unittest.main()
