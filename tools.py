from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from career_store import CareerStore
    from rag_agent import RagAssistant


# ---- 输入 Schema ----

class SearchKnowledgeInput(BaseModel):
    query: str = Field(description="检索查询内容")
    top_k: int = Field(default=5, description="返回结果数量")


class AskKnowledgeInput(BaseModel):
    question: str = Field(description="要问的问题")
    top_k: int = Field(default=4, description="参考文档数量")


class GetJobInput(BaseModel):
    job_id: str = Field(description="岗位 ID")


class AnalyzeMatchInput(BaseModel):
    job_id: str = Field(description="岗位 ID")


class ListEvidenceInput(BaseModel):
    category: str = Field(default="", description="按类别筛选，可选 education/skill/project/award/availability")


class TailorResumeInput(BaseModel):
    job_id: str = Field(description="岗位 ID")
    category: str = Field(default="project", description="定制的简历部分")


def create_tools(rag_assistant: RagAssistant, career_store: CareerStore) -> list:
    """创建所有可用工具。"""

    def _search_knowledge(query: str, top_k: int = 5) -> str:
        """检索参考资料库中的相关内容。用于查找简历写作规范、公司资料等参考信息。"""
        try:
            results = rag_assistant.search(query, top_k=top_k)
            if not results:
                return "未找到相关参考资料。"
            formatted = []
            for i, item in enumerate(results, 1):
                source = item.get("source", "未知来源")
                content = item.get("content", "")
                score = item.get("score", 0)
                formatted.append(f"[{i}] 来源: {source} (相关度: {score:.2f})\n{content}")
            return "\n\n".join(formatted)
        except Exception as e:
            return f"检索失败: {str(e)}"

    def _ask_knowledge(question: str, top_k: int = 4) -> str:
        """基于参考资料库回答问题。用于查询简历写作建议、面试技巧等信息。"""
        try:
            result = rag_assistant.ask(question, top_k=top_k)
            answer = result.get("answer", "无法回答该问题。")
            sources = result.get("sources", [])
            if sources:
                source_list = "\n".join(
                    f"- {s.get('source', '未知')}" for s in sources[:3]
                )
                return f"{answer}\n\n参考来源:\n{source_list}"
            return answer
        except Exception as e:
            return f"问答失败: {str(e)}"

    def _list_jobs() -> str:
        """列出所有已保存的岗位信息。"""
        try:
            jobs = career_store.list_job_postings()
            if not jobs:
                return "暂无保存的岗位信息。"
            formatted = []
            for job in jobs:
                skills = ", ".join(job.required_skills[:5]) if job.required_skills else "无"
                formatted.append(
                    f"- {job.job_id}: {job.company} · {job.title} ({job.location})\n"
                    f"  必备技能: {skills}"
                )
            return "\n".join(formatted)
        except Exception as e:
            return f"获取岗位列表失败: {str(e)}"

    def _get_job(job_id: str) -> str:
        """获取指定岗位的详细信息。"""
        try:
            jobs = career_store.list_job_postings()
            job = next((j for j in jobs if j.job_id == job_id), None)
            if not job:
                return f"未找到岗位 {job_id}"
            return (
                f"公司: {job.company}\n"
                f"岗位: {job.title}\n"
                f"地点: {job.location}\n"
                f"JD原文:\n{job.raw_description[:500]}...\n"
                f"必备技能: {', '.join(job.required_skills)}\n"
                f"加分技能: {', '.join(job.preferred_skills)}"
            )
        except Exception as e:
            return f"获取岗位信息失败: {str(e)}"

    def _analyze_match(job_id: str) -> str:
        """分析岗位匹配度，返回匹配分数和建议。用于评估个人能力与岗位要求的匹配程度。"""
        try:
            analysis = career_store.analyze_job_match(job_id)
            result = [
                f"匹配分数: {analysis.score:.1f}/100",
                f"已覆盖必备技能: {', '.join(analysis.matched_requirements) or '暂无'}",
                f"缺少必备技能: {', '.join(analysis.missing_requirements) or '暂无'}",
                f"已覆盖加分技能: {', '.join(analysis.matched_preferred_skills) or '暂无'}",
                f"缺少加分技能: {', '.join(analysis.missing_preferred_skills) or '暂无'}",
            ]
            if analysis.resume_suggestions:
                result.append("\n建议:")
                for s in analysis.resume_suggestions:
                    result.append(f"- {s}")
            return "\n".join(result)
        except Exception as e:
            return f"分析匹配度失败: {str(e)}"

    def _list_evidence(category: str = "") -> str:
        """列出个人履历证据。可按类别筛选（education/skill/project/award/availability）。"""
        try:
            evidence_list = career_store.list_profile_evidence()
            if category:
                evidence_list = [e for e in evidence_list if e.category == category]
            if not evidence_list:
                return "暂无履历证据。"
            formatted = []
            for e in evidence_list:
                verified = "已确认" if e.verified else "待确认"
                formatted.append(
                    f"- [{e.category}] {e.content[:80]}... ({verified})"
                )
            return "\n".join(formatted)
        except Exception as e:
            return f"获取履历证据失败: {str(e)}"

    def _tailor_resume(job_id: str, category: str = "project") -> str:
        """基于岗位要求定制简历表述。生成针对特定岗位的简历优化建议。"""
        try:
            jobs = career_store.list_job_postings()
            job = next((j for j in jobs if j.job_id == job_id), None)
            if not job:
                return f"未找到岗位 {job_id}"

            evidence_list = career_store.list_profile_evidence()
            verified = [e for e in evidence_list if e.verified]
            if not verified:
                return "暂无已确认的履历证据，无法定制简历。"

            evidence_texts = [f"[{e.category}] {e.content}" for e in verified]
            result = rag_assistant.tailor_resume(
                job_description=job.raw_description,
                evidence=evidence_texts,
                current_text="",
                request=f"为{job.title}岗位定制{category}部分的简历表述",
            )
            return (
                f"适配判断:\n{result.fit_assessment}\n\n"
                f"推荐表述:\n{result.recommended_text}\n\n"
                f"证据依据:\n{result.evidence_basis}\n\n"
                f"缺口提示:\n{result.gap_notes}"
            )
        except Exception as e:
            return f"定制简历失败: {str(e)}"

    def _get_profile() -> str:
        """获取个人档案基本信息。"""
        try:
            profile = career_store.load_candidate_profile()
            fields = [
                ("姓名", profile.name),
                ("电话", profile.phone),
                ("邮箱", profile.email),
                ("城市", profile.city),
                ("求职意向", profile.target_role),
                ("期望地点", profile.preferred_locations),
                ("个人主页", profile.homepage),
                ("个人简介", profile.summary[:200] if profile.summary else ""),
            ]
            return "\n".join(f"{k}: {v}" for k, v in fields if v)
        except Exception as e:
            return f"获取个人档案失败: {str(e)}"

    return [
        StructuredTool.from_function(
            func=_search_knowledge,
            name="search_knowledge",
            description="检索参考资料库中的相关内容。用于查找简历写作规范、公司资料等参考信息。",
            args_schema=SearchKnowledgeInput,
        ),
        StructuredTool.from_function(
            func=_ask_knowledge,
            name="ask_knowledge",
            description="基于参考资料库回答问题。用于查询简历写作建议、面试技巧等信息。",
            args_schema=AskKnowledgeInput,
        ),
        StructuredTool.from_function(
            func=_list_jobs,
            name="list_jobs",
            description="列出所有已保存的岗位信息。",
        ),
        StructuredTool.from_function(
            func=_get_job,
            name="get_job",
            description="获取指定岗位的详细信息。",
            args_schema=GetJobInput,
        ),
        StructuredTool.from_function(
            func=_analyze_match,
            name="analyze_match",
            description="分析岗位匹配度，返回匹配分数和建议。用于评估个人能力与岗位要求的匹配程度。",
            args_schema=AnalyzeMatchInput,
        ),
        StructuredTool.from_function(
            func=_list_evidence,
            name="list_evidence",
            description="列出个人履历证据。可按类别筛选（education/skill/project/award/availability）。",
            args_schema=ListEvidenceInput,
        ),
        StructuredTool.from_function(
            func=_tailor_resume,
            name="tailor_resume",
            description="基于岗位要求定制简历表述。生成针对特定岗位的简历优化建议。",
            args_schema=TailorResumeInput,
        ),
        StructuredTool.from_function(
            func=_get_profile,
            name="get_profile",
            description="获取个人档案基本信息。",
        ),
    ]
