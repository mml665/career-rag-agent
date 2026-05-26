import tempfile
import unittest
from pathlib import Path

from career_store import APPLICATION_STATUSES, CareerStore


class CareerStoreTests(unittest.TestCase):
    def test_candidate_profile_saves_basic_contact_and_target_information(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))

            saved = store.save_candidate_profile(
                name="张三",
                phone="13800000000",
                email="candidate@example.com",
                city="上海",
                target_role="AI Agent 实习生",
                preferred_locations="上海 / 杭州",
                homepage="https://github.com/example",
                summary="关注 RAG 与 Agent 应用开发。",
            )
            loaded = store.load_candidate_profile()

            self.assertEqual(saved.email, "candidate@example.com")
            self.assertEqual(loaded.name, "张三")
            self.assertEqual(loaded.target_role, "AI Agent 实习生")

    def test_basic_profile_can_be_saved_before_resume_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))

            store.save_candidate_profile(name="张三", target_role="AI Agent 实习生")
            records = store.save_profile_sections({})

            self.assertEqual(records, [])
            self.assertEqual(store.load_candidate_profile().name, "张三")

    def test_profile_evidence_is_saved_updated_and_deleted_without_a_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            evidence = store.add_profile_evidence(
                category="project",
                content="实现向量检索与来源展示。",
                source_file="resume.md",
            )

            records = store.list_profile_evidence()
            self.assertEqual(records[0].title, "")
            self.assertTrue(records[0].verified)
            updated = store.update_profile_evidence(
                evidence.evidence_id,
                category="skill",
                content="熟悉 RAG 检索与引用展示。",
                verified=False,
            )
            self.assertEqual(updated.category, "skill")
            self.assertFalse(updated.verified)
            self.assertEqual(store.list_profile_evidence()[0].content, "熟悉 RAG 检索与引用展示。")
            self.assertTrue(store.delete_profile_evidence(evidence.evidence_id))
            self.assertEqual(store.list_profile_evidence(), [])

    def test_profile_sections_are_saved_as_one_editable_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            store.add_profile_evidence(category="project", content="旧项目描述。")
            store.add_profile_evidence(category="project", content="另一条项目描述。")

            records = store.save_profile_sections(
                {
                    "education": "某大学，计算机相关专业。",
                    "skill": "Python、RAG、LangChain。",
                    "project": "完成资料问答 Agent 项目。",
                    "award": "",
                    "availability": "每周可实习四天。",
                },
                source_file="resume.pdf",
            )

            self.assertEqual(
                [record.category for record in records],
                ["education", "skill", "project", "availability"],
            )
            self.assertEqual(
                [record.content for record in records if record.category == "project"],
                ["完成资料问答 Agent 项目。"],
            )
            self.assertTrue(all(record.source_file == "resume.pdf" for record in records))

    def test_job_posting_is_saved_loaded_and_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="上海",
                raw_description="需要 RAG 与 Python 能力。",
                required_skills=["RAG", "Python"],
                preferred_skills=["FastAPI"],
            )

            records = store.list_job_postings()
            self.assertEqual(records[0].required_skills, ["RAG", "Python"])
            self.assertTrue(store.delete_job_posting(job.job_id))
            self.assertEqual(store.list_job_postings(), [])

    def test_required_fields_are_validated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))

            with self.assertRaises(ValueError):
                store.add_profile_evidence(category="project", content="")
            with self.assertRaises(ValueError):
                store.add_job_posting(company="", title="intern", location="", raw_description="jd")

    def test_match_analysis_only_uses_verified_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            verified = store.add_profile_evidence(
                category="project",
                content="使用 Python 与 RAG 完成资料检索问答。",
                verified=True,
            )
            store.add_profile_evidence(
                category="skill",
                content="熟悉 FastAPI。",
                verified=False,
            )
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="上海",
                raw_description="需要 Python、RAG，熟悉 FastAPI 优先。",
                required_skills=["Python", "RAG"],
                preferred_skills=["FastAPI"],
            )

            analysis = store.analyze_job_match(job.job_id)

            self.assertEqual(analysis.score, 70.0)
            self.assertEqual(analysis.matched_requirements, ["Python", "RAG"])
            self.assertEqual(analysis.missing_preferred_skills, ["FastAPI"])
            self.assertEqual(analysis.evidence_ids, [verified.evidence_id])
            self.assertEqual(store.list_match_analyses(job.job_id)[0].analysis_id, analysis.analysis_id)

    def test_deleting_a_job_removes_its_analysis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            store.analyze_job_match(job.job_id)

            self.assertTrue(store.delete_job_posting(job.job_id))
            self.assertEqual(store.list_match_analyses(job.job_id), [])

    def test_profile_update_marks_existing_match_analysis_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            evidence = store.add_profile_evidence(category="skill", content="熟悉 RAG。")
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            analysis = store.analyze_job_match(job.job_id)

            store.update_profile_evidence(
                evidence.evidence_id,
                category="skill",
                content="熟悉 Python。",
            )

            historical = store.list_match_analyses(job.job_id)[0]
            self.assertEqual(historical.analysis_id, analysis.analysis_id)
            self.assertTrue(historical.is_stale)
            self.assertTrue(historical.invalidated_at)

    def test_profile_document_save_marks_existing_match_analysis_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            store.save_profile_sections({"skill": "熟悉 RAG。"})
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            analysis = store.analyze_job_match(job.job_id)

            store.save_profile_sections({"skill": "熟悉 Python。"})

            historical = store.list_match_analyses(job.job_id)[0]
            self.assertEqual(historical.analysis_id, analysis.analysis_id)
            self.assertTrue(historical.is_stale)

    def test_deleting_profile_section_preserves_analysis_as_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            store.add_profile_evidence(category="project", content="第一条项目经历。")
            store.add_profile_evidence(category="project", content="第二条项目经历。")
            store.add_profile_evidence(category="skill", content="熟悉 RAG。")
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            analysis = store.analyze_job_match(job.job_id)

            self.assertTrue(store.delete_profile_section("project"))

            categories = [record.category for record in store.list_profile_evidence()]
            self.assertEqual(categories, ["skill"])
            historical = store.list_match_analyses(job.job_id)[0]
            self.assertEqual(historical.analysis_id, analysis.analysis_id)
            self.assertTrue(historical.is_stale)

    def test_deleting_one_profile_item_preserves_other_content_in_same_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            original = store.add_profile_evidence(category="project", content="原始项目经历。")
            adopted = store.add_profile_evidence(
                category="project",
                content="定制后的项目表述。",
                source_file="简历定制：Agent 实习生",
            )

            self.assertTrue(store.delete_profile_evidence(adopted.evidence_id))

            remaining = store.list_profile_evidence()
            self.assertEqual([record.evidence_id for record in remaining], [original.evidence_id])
            self.assertEqual(remaining[0].content, "原始项目经历。")

    def test_adopting_customized_resume_evidence_keeps_match_analysis_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            store.add_profile_evidence(category="project", content="实现 RAG 资料问答。")
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            analysis = store.analyze_job_match(job.job_id)

            store.add_profile_evidence(
                category="project",
                content="基于 DashScope 完成 RAG 检索问答流程。",
                source_file="简历定制：Example · Agent 实习生",
            )

            historical = store.list_match_analyses(job.job_id)
            self.assertEqual(len(historical), 1)
            self.assertEqual(historical[0].analysis_id, analysis.analysis_id)
            self.assertTrue(historical[0].is_stale)

    def test_saving_unchanged_profile_sections_keeps_match_analysis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            store.save_profile_sections({"skill": "熟悉 RAG。"})
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            analysis = store.analyze_job_match(job.job_id)

            store.save_profile_sections({"skill": "熟悉 RAG。"})

            self.assertEqual(store.list_match_analyses(job.job_id)[0].analysis_id, analysis.analysis_id)

    def test_application_record_can_be_saved_updated_and_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
            )

            record = store.add_application(
                job_id=job.job_id,
                status="planned",
                resume_version="v1",
                notes="待修改简历",
            )
            updated = store.update_application(
                record.application_id,
                status="submitted",
                resume_version="v2",
                submitted_at="2026-05-26",
                notes="官网投递",
            )

            self.assertIn(updated.status, APPLICATION_STATUSES)
            self.assertEqual(updated.status, "submitted")
            self.assertEqual(updated.resume_version, "v2")
            self.assertTrue(store.delete_application(record.application_id))
            self.assertEqual(store.list_applications(), [])

    def test_resume_version_can_be_saved_linked_to_application_and_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
            )
            version = store.add_resume_version(
                job_id=job.job_id,
                name="Example-Agent-v1",
                content="实现 RAG 资料问答。",
                fit_assessment="匹配。",
            )
            application = store.add_application(
                job_id=job.job_id,
                resume_version=version.name,
                resume_version_id=version.version_id,
            )

            self.assertEqual(store.list_resume_versions(job.job_id)[0].name, version.name)
            self.assertEqual(application.resume_version_id, version.version_id)
            self.assertTrue(store.delete_resume_version(version.version_id))
            self.assertEqual(store.list_resume_versions(job.job_id), [])
            remaining_application = store.list_applications()[0]
            self.assertEqual(remaining_application.resume_version_id, "")
            self.assertEqual(remaining_application.resume_version, version.name)

    def test_hybrid_match_enhancement_preserves_keyword_score(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            evidence = store.add_profile_evidence(category="skill", content="熟悉 RAG。")
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
                required_skills=["RAG"],
            )
            baseline = store.analyze_job_match(job.job_id)

            analysis = store.enhance_match_analysis(
                baseline.analysis_id,
                semantic_score=80.0,
                semantic_evidence_ids=[evidence.evidence_id],
                model_explanation="证据支持 RAG 能力。",
            )

            self.assertEqual(analysis.analysis_type, "hybrid")
            self.assertEqual(analysis.keyword_score, 100.0)
            self.assertEqual(analysis.semantic_score, 80.0)
            self.assertEqual(analysis.score, 92.0)

    def test_deleting_a_job_removes_its_application_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir))
            job = store.add_job_posting(
                company="Example",
                title="Agent 实习生",
                location="",
                raw_description="需要 RAG。",
            )
            store.add_application(job_id=job.job_id)

            store.delete_job_posting(job.job_id)

            self.assertEqual(store.list_applications(), [])


if __name__ == "__main__":
    unittest.main()
