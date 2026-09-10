import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas

from document_intelligence import inspect_document, split_markdown_by_headings
from rag_agent import RagAssistant, RagConfig


class DocumentIntelligenceTests(unittest.TestCase):
    def test_markdown_is_split_by_heading_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "guide.md"
            text = "# 简历优化\n\n总览\n\n## 项目经历\n\n项目内容\n\n### Agent 项目\n\nRAG 内容"

            docs = split_markdown_by_headings(path, text)

            self.assertEqual(docs[0].metadata["heading_path"], "简历优化")
            self.assertEqual(docs[1].metadata["heading_path"], "简历优化 > 项目经历")
            self.assertEqual(docs[2].metadata["heading_path"], "简历优化 > 项目经历 > Agent 项目")

    def test_text_pdf_is_classified_without_ocr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "resume.pdf"
            c = canvas.Canvas(str(path))
            c.drawString(72, 720, "AI Agent resume with FastAPI RAG LangChain and Chroma.")
            c.drawString(72, 700, "Project experience and internship details.")
            c.save()

            report = inspect_document(path)

            self.assertEqual(report.file_type, "pdf")
            self.assertTrue(report.has_text_layer)
            self.assertFalse(report.needs_ocr)
            self.assertIn(report.document_type, {"text_pdf", "low_text_pdf"})

    def test_markdown_load_keeps_heading_metadata_after_chunking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assistant = RagAssistant(
                RagConfig(
                    docs_dir=root / "documents",
                    upload_dir=root / "uploads",
                    chroma_dir=root / "chroma",
                    history_path=root / "history.jsonl",
                    chunk_size=80,
                    chunk_overlap=10,
                )
            )
            path = assistant.config.docs_dir / "notes.md"
            path.write_text("# 求职策略\n\n## Agent 岗位\n\n需要 RAG、Tool Calling 和 FastAPI。", encoding="utf-8")

            docs = assistant._load_document(path)
            chunks = assistant._split_documents(docs)

            self.assertTrue(any(chunk.metadata["heading_path"] == "求职策略 > Agent 岗位" for chunk in chunks))
            self.assertTrue(all(chunk.metadata["document_type"] == "structured_text" for chunk in chunks))

    def test_scanned_pdf_upload_returns_ocr_hint_when_no_text_is_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assistant = RagAssistant(
                RagConfig(
                    resume_upload_dir=root / "resume_uploads",
                    job_upload_dir=root / "job_uploads",
                    docs_dir=root / "documents",
                    upload_dir=root / "uploads",
                    chroma_dir=root / "chroma",
                    history_path=root / "history.jsonl",
                )
            )
            path = root / "blank.pdf"
            c = canvas.Canvas(str(path))
            c.showPage()
            c.save()

            with self.assertRaises(ValueError) as ctx:
                assistant.extract_resume_upload(path.name, path.read_bytes())

            self.assertIn("未能从简历中读取到文本内容", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
