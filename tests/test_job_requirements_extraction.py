import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rag_agent import RagAssistant, RagConfig


class StubChatModel:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, _messages):
        return SimpleNamespace(content=self.content)


class StubEmbeddings:
    def embed_documents(self, _texts):
        return [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]


class JobRequirementsExtractionTests(unittest.TestCase):
    def build_assistant(self, root: Path) -> RagAssistant:
        return RagAssistant(
            RagConfig(
                docs_dir=root / "documents",
                upload_dir=root / "uploads",
                resume_upload_dir=root / "resume_uploads",
                job_upload_dir=root / "job_uploads",
                chroma_dir=root / "chroma",
                history_path=root / "history.jsonl",
            )
        )

    def test_parses_json_fence_and_removes_duplicate_items(self):
        extraction = RagAssistant.parse_job_requirements_response(
            """```json
            {
              "required_skills": ["Python", "RAG", "Python"],
              "preferred_skills": ["FastAPI"],
              "internship_requirements": ["每周到岗 4 天"]
            }
            ```"""
        )

        self.assertEqual(extraction.required_skills, ["Python", "RAG"])
        self.assertEqual(extraction.preferred_skills, ["FastAPI"])
        self.assertEqual(extraction.internship_requirements, ["每周到岗 4 天"])

    def test_extract_job_requirements_calls_model_and_parses_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            response = (
                '{"required_skills":["Python"],"preferred_skills":[],'
                '"internship_requirements":["连续实习 3 个月"]}'
            )
            assistant._llm = lambda: StubChatModel(response)

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                extraction = assistant.extract_job_requirements("要求熟悉 Python，可实习三个月。")

            self.assertEqual(extraction.required_skills, ["Python"])
            self.assertEqual(extraction.internship_requirements, ["连续实习 3 个月"])

    def test_extract_job_posting_text_preserves_original_jd_and_extracts_header(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant._llm = lambda: StubChatModel(
                '{"company":"示例科技","title":"Agent 实习生","location":"杭州",'
                '"required_skills":["Python","RAG"],"preferred_skills":["FastAPI"],'
                '"internship_requirements":["每周到岗 4 天"]}'
            )
            raw_description = "示例科技招聘 Agent 实习生，工作地点杭州，要求 Python 与 RAG。"

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                extraction = assistant.extract_job_posting_text(raw_description)

            self.assertEqual(extraction.company, "示例科技")
            self.assertEqual(extraction.title, "Agent 实习生")
            self.assertEqual(extraction.raw_description, raw_description)
            self.assertEqual(extraction.required_skills, ["Python", "RAG"])

    def test_extract_job_upload_reads_text_file_and_keeps_uploaded_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assistant = self.build_assistant(root)
            assistant._llm = lambda: StubChatModel(
                '{"company":"示例科技","title":"数据实习生","location":"",'
                '"required_skills":["Python"],"preferred_skills":[],"internship_requirements":[]}'
            )

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                extraction = assistant.extract_job_upload(
                    "岗位说明.txt", "要求熟悉 Python。".encode("utf-8")
                )

            self.assertIn("Python", extraction.raw_description)
            self.assertTrue((root / "job_uploads" / "岗位说明.txt").exists())

    def test_rejects_non_list_extraction_field(self):
        with self.assertRaises(RuntimeError):
            RagAssistant.parse_job_requirements_response(
                '{"required_skills":"Python","preferred_skills":[],"internship_requirements":[]}'
            )

    def test_parse_resume_profile_response_extracts_profile_sections(self):
        extraction = RagAssistant.parse_resume_profile_response(
            '{"name":"张三","email":"candidate@example.com","skill":"Python, RAG",'
            '"project":"完成资料问答项目。"}'
        )

        self.assertEqual(extraction.name, "张三")
        self.assertEqual(extraction.skill, "Python, RAG")
        self.assertEqual(extraction.education, "")

    def test_extract_resume_text_calls_model_and_parses_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant._llm = lambda: StubChatModel(
                '{"name":"张三","target_role":"Agent 实习生","project":"实现 RAG。"}'
            )

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                extraction = assistant.extract_resume_text("张三\\n项目：实现 RAG。")

            self.assertEqual(extraction.target_role, "Agent 实习生")
            self.assertEqual(extraction.project, "实现 RAG。")

    def test_tailor_resume_calls_model_with_verified_evidence_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant._llm = lambda: StubChatModel(
                '{"fit_assessment":"匹配 RAG 要求。",'
                '"recommended_text":"使用 Python 完成 RAG 资料问答项目。",'
                '"evidence_basis":"项目证据中明确包含 Python 和 RAG。",'
                '"gap_notes":"暂无。"}'
            )

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                result = assistant.tailor_resume(
                    job_description="需要 Python 与 RAG。",
                    evidence=["使用 Python 完成 RAG 资料检索问答。"],
                    current_text="完成资料问答。",
                )

            self.assertIn("RAG", result.recommended_text)
            self.assertNotIn("证据", result.recommended_text)

    def test_parse_resume_tailoring_response_separates_review_from_resume_text(self):
        result = RagAssistant.parse_resume_tailoring_response(
            """```json
            {
              "fit_assessment": "匹配主要技能要求。",
              "recommended_text": "使用 LangChain 与 Chroma 实现 RAG 检索问答。",
              "evidence_basis": "已确认项目包含 RAG 实现经历。",
              "gap_notes": "暂无 FastAPI 证据。"
            }
            ```"""
        )

        self.assertEqual(
            result.recommended_text, "使用 LangChain 与 Chroma 实现 RAG 检索问答。"
        )
        self.assertIn("FastAPI", result.gap_notes)

    def test_rejects_resume_tailoring_result_without_recommended_text(self):
        with self.assertRaises(RuntimeError):
            RagAssistant.parse_resume_tailoring_response(
                '{"fit_assessment":"匹配","recommended_text":"",'
                '"evidence_basis":"证据","gap_notes":"缺口"}'
            )

    def test_tailor_resume_requires_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))

            with self.assertRaises(ValueError):
                assistant.tailor_resume(job_description="需要 Python。", evidence=[])

    def test_semantic_match_scores_evidence_and_generates_explanation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))
            assistant._embeddings = lambda: StubEmbeddings()
            assistant._llm = lambda: StubChatModel("证据支持 RAG，尚缺部署经验。")

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                result = assistant.analyze_semantic_match(
                    job_description="需要 RAG 开发能力。",
                    evidence=[("evidence_a", "实现 RAG。"), ("evidence_b", "熟悉绘图。")],
                    keyword_summary="RAG 已覆盖。",
                )

            self.assertEqual(result.evidence_ids[0], "evidence_a")
            self.assertEqual(result.semantic_score, 50.0)
            self.assertIn("RAG", result.model_explanation)


if __name__ == "__main__":
    unittest.main()
