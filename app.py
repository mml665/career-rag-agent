from __future__ import annotations

import re

import streamlit as st

from career_store import APPLICATION_STATUSES, PROFILE_CATEGORIES, CareerStore, JobPosting
from rag_agent import RagAssistant, RagConfig


st.set_page_config(page_title="智能选岗及简历定制 Agent", layout="wide")

PAGES = ["个人档案", "岗位库", "匹配分析", "简历定制", "投递记录", "参考资料库"]
LIBRARY_PAGES = ["资料管理", "资料问答", "检索调试", "摘要与历史"]
JOB_FORM_KEYS = (
    "new_job_company",
    "new_job_title",
    "new_job_location",
    "new_job_source_url",
    "new_job_raw_description",
    "new_job_required_skills",
    "new_job_preferred_skills",
    "new_job_requirements",
)
PROFILE_DRAFT_KEYS = {
    "education": "profile_draft_education",
    "skill": "profile_draft_skill",
    "project": "profile_draft_project",
    "award": "profile_draft_award",
    "availability": "profile_draft_availability",
    "source_file": "profile_draft_source_file",
    "verified": "profile_draft_verified",
}
PROFILE_BASIC_KEYS = {
    "name": "profile_basic_name",
    "phone": "profile_basic_phone",
    "email": "profile_basic_email",
    "city": "profile_basic_city",
    "target_role": "profile_basic_target_role",
    "preferred_locations": "profile_basic_preferred_locations",
    "homepage": "profile_basic_homepage",
    "summary": "profile_basic_summary",
}


def build_assistant() -> RagAssistant:
    return RagAssistant(
        RagConfig(
            chunk_size=st.session_state.get("chunk_size", RagConfig.chunk_size),
            chunk_overlap=st.session_state.get("chunk_overlap", RagConfig.chunk_overlap),
            top_k=st.session_state.get("top_k", RagConfig.top_k),
            min_relevance_score=st.session_state.get(
                "min_relevance_score", RagConfig.min_relevance_score
            ),
        )
    )


def parse_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,，、]+", value) if item.strip()]


def format_job(job: JobPosting) -> str:
    label = f"{job.company} · {job.title}"
    return f"{label} · {job.location}" if job.location else label


def sync_index_after_document_change() -> str:
    assistant.reset_index()
    if not assistant.is_configured():
        return "文件已删除，旧索引已清空。配置 DASHSCOPE_API_KEY 后请重建索引。"
    count = assistant.ingest_all()
    return f"文件已删除，索引已同步，当前包含 {count} 个资料片段。"


def clear_job_form() -> None:
    for key in JOB_FORM_KEYS:
        st.session_state.pop(key, None)


def clear_profile_draft() -> None:
    for category, key in PROFILE_DRAFT_KEYS.items():
        st.session_state[key] = True if category == "verified" else ""


def prefill_extracted_resume(extraction: dict) -> None:
    for field, key in PROFILE_BASIC_KEYS.items():
        st.session_state[key] = extraction.get(field, "")
    for category in PROFILE_CATEGORIES:
        st.session_state[PROFILE_DRAFT_KEYS[category]] = extraction.get(category, "")
    st.session_state[PROFILE_DRAFT_KEYS["source_file"]] = extraction.get("source_file", "")
    st.session_state[PROFILE_DRAFT_KEYS["verified"]] = False


def prefill_extracted_job(extraction: dict) -> None:
    text_fields = {
        "company": "new_job_company",
        "title": "new_job_title",
        "location": "new_job_location",
        "raw_description": "new_job_raw_description",
    }
    for field, key in text_fields.items():
        if extraction.get(field):
            st.session_state[key] = extraction[field]
    for field, key in (
        ("required_skills", "new_job_required_skills"),
        ("preferred_skills", "new_job_preferred_skills"),
        ("internship_requirements", "new_job_requirements"),
    ):
        st.session_state[key] = "\n".join(extraction.get(field, []))


def set_message(message: str) -> None:
    st.session_state.page_message = message


def show_message() -> None:
    if message := st.session_state.pop("page_message", None):
        st.success(message)


def refresh_page() -> None:
    st.rerun()


def show_analysis(analysis, evidence_by_id: dict) -> None:
    if analysis.is_stale:
        st.warning("这是一条历史分析：个人档案已在分析后发生变化，请重新运行匹配生成当前结果。")
    if analysis.analysis_type == "hybrid":
        overall, keyword, semantic = st.columns(3)
        overall.metric("综合匹配分数", f"{analysis.score:.1f}")
        keyword.metric("关键词分数", f"{analysis.keyword_score:.1f}")
        semantic.metric("语义分数", f"{analysis.semantic_score:.1f}")
        st.caption("混合分析：关键词覆盖占 60%，Embedding 语义匹配占 40%；模型解释仅基于证据。")
    else:
        st.metric("技能匹配分数", f"{analysis.score:.1f}")
        st.caption("关键词基线：仅使用已确认履历；必备技能占 70%，加分技能占 30%。")
    left, right = st.columns(2)
    left.markdown(f"**已覆盖必备技能：** {', '.join(analysis.matched_requirements) or '暂无'}")
    left.markdown(f"**已覆盖加分技能：** {', '.join(analysis.matched_preferred_skills) or '暂无'}")
    right.markdown(f"**缺少必备证据：** {', '.join(analysis.missing_requirements) or '暂无'}")
    right.markdown(f"**缺少加分证据：** {', '.join(analysis.missing_preferred_skills) or '暂无'}")
    if analysis.evidence_map:
        st.markdown("**命中证据**")
        for skill, evidence_ids in analysis.evidence_map.items():
            contents = [
                evidence_by_id[evidence_id].content[:60]
                for evidence_id in evidence_ids
                if evidence_id in evidence_by_id
            ]
            st.write(f"{skill}：{'；'.join(contents)}")
    for suggestion in analysis.resume_suggestions:
        st.info(suggestion)
    if analysis.analysis_type == "hybrid" and analysis.model_explanation:
        st.markdown("**模型解释**")
        st.write(analysis.model_explanation)


def show_saved_resume_versions(job_by_id: dict[str, JobPosting]) -> None:
    versions = career_store.list_resume_versions()
    if not versions:
        return
    st.divider()
    st.subheader("已保存简历版本")
    for version in reversed(versions):
        version_job = job_by_id.get(version.job_id)
        if not version_job:
            continue
        with st.expander(f"{version.name} · {format_job(version_job)}"):
            st.markdown(f"**{PROFILE_CATEGORIES[version.target_category]}**")
            st.write(version.content)
            st.caption(f"创建时间：{version.created_at}")
            if st.button("删除版本", key=f"delete_resume_version_{version.version_id}"):
                career_store.delete_resume_version(version.version_id)
                set_message("定制简历版本已删除；已解除投递记录中的版本关联。")
                refresh_page()


with st.sidebar:
    st.subheader("参考资料检索参数")
    st.session_state.chunk_size = st.slider("Chunk size", 300, 1800, 700, 50)
    st.session_state.chunk_overlap = st.slider("Overlap", 0, 400, 120, 20)
    st.session_state.top_k = st.slider("Top K", 1, 10, 4, 1)
    st.session_state.min_relevance_score = st.slider(
        "最低相关性", 0.0, 1.0, float(RagConfig.min_relevance_score), 0.05
    )

assistant = build_assistant()
career_store = CareerStore()


@st.fragment
def render_profile_page() -> None:
    show_message()
    st.subheader("个人档案")
    if st.session_state.pop("reset_profile_draft", False):
        clear_profile_draft()
    st.session_state.setdefault(PROFILE_DRAFT_KEYS["verified"], True)
    candidate = career_store.load_candidate_profile()
    for field, key in PROFILE_BASIC_KEYS.items():
        st.session_state.setdefault(key, getattr(candidate, field))
    if extraction := st.session_state.pop("resume_extraction_prefill", None):
        prefill_extracted_resume(extraction)
    evidence_records = career_store.list_profile_evidence()
    sections = {
        category: "\n\n".join(
            evidence.content for evidence in evidence_records if evidence.category == category
        )
        for category in PROFILE_CATEGORIES
    }
    source_files = list(
        dict.fromkeys(evidence.source_file for evidence in evidence_records if evidence.source_file)
    )
    all_verified = all(evidence.verified for evidence in evidence_records) if evidence_records else True
    st.markdown("**导入已有简历**")
    resume_upload = st.file_uploader(
        "上传 PDF / Markdown / TXT 简历",
        type=["pdf", "md", "markdown", "txt"],
        key="resume_profile_upload",
    )
    if resume_upload and st.button("解析并回填草稿", type="primary"):
        if not assistant.is_configured():
            st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
        else:
            try:
                with st.spinner("正在从简历提取个人档案信息..."):
                    parsed = assistant.extract_resume_upload(
                        resume_upload.name, resume_upload.getvalue()
                    )
                st.session_state.resume_extraction_prefill = {
                    **parsed.__dict__,
                    "source_file": resume_upload.name,
                }
                set_message("简历已解析并回填为草稿，请核对后分别保存基本信息与履历内容。")
                refresh_page()
            except (RuntimeError, ValueError) as exc:
                st.error(f"解析失败：{exc}")
    st.markdown("**基本信息**")
    with st.form("candidate_profile_form"):
        identity_first, identity_second = st.columns(2)
        name = identity_first.text_input("姓名", key=PROFILE_BASIC_KEYS["name"])
        phone = identity_second.text_input("手机号", key=PROFILE_BASIC_KEYS["phone"])
        email = identity_first.text_input("邮箱", key=PROFILE_BASIC_KEYS["email"])
        city = identity_second.text_input("当前所在地", key=PROFILE_BASIC_KEYS["city"])
        target_role = identity_first.text_input("求职意向", key=PROFILE_BASIC_KEYS["target_role"])
        preferred_locations = identity_second.text_input(
            "期望工作地点", key=PROFILE_BASIC_KEYS["preferred_locations"]
        )
        homepage = st.text_input("个人主页 / GitHub / 作品链接", key=PROFILE_BASIC_KEYS["homepage"])
        summary = st.text_area("个人简介", height=90, key=PROFILE_BASIC_KEYS["summary"])
        save_basic_profile = st.form_submit_button("保存基本信息", type="primary")
    if save_basic_profile:
        career_store.save_candidate_profile(
            name=name,
            phone=phone,
            email=email,
            city=city,
            target_role=target_role,
            preferred_locations=preferred_locations,
            homepage=homepage,
            summary=summary,
        )
        set_message("基本信息已保存。")
        refresh_page()

    st.markdown("**履历内容**")
    draft_actions = st.columns([1, 1, 4])
    if evidence_records and draft_actions[0].button("载入已有履历"):
        for category in PROFILE_CATEGORIES:
            st.session_state[PROFILE_DRAFT_KEYS[category]] = sections[category]
        st.session_state[PROFILE_DRAFT_KEYS["source_file"]] = "；".join(source_files)
        st.session_state[PROFILE_DRAFT_KEYS["verified"]] = all_verified
        refresh_page()
    if draft_actions[1].button("清空输入"):
        clear_profile_draft()
        refresh_page()
    with st.form("profile_sections_form"):
        first, second = st.columns(2)
        education = first.text_area("教育背景", height=115, key=PROFILE_DRAFT_KEYS["education"])
        skill = second.text_area("技能", height=115, key=PROFILE_DRAFT_KEYS["skill"])
        project = st.text_area("项目经历", height=180, key=PROFILE_DRAFT_KEYS["project"])
        third, fourth = st.columns(2)
        award = third.text_area("奖项 / 成果", height=115, key=PROFILE_DRAFT_KEYS["award"])
        availability = fourth.text_area(
            "实习条件", height=115, key=PROFILE_DRAFT_KEYS["availability"]
        )
        source_file = st.text_input("来源文件", key=PROFILE_DRAFT_KEYS["source_file"])
        verified = st.checkbox(
            "以上履历内容均已确认，可用于简历建议",
            key=PROFILE_DRAFT_KEYS["verified"],
        )
        save_resume = st.form_submit_button("保存履历内容", type="primary")
    if save_resume:
        resume_sections = {
            "education": education,
            "skill": skill,
            "project": project,
            "award": award,
            "availability": availability,
        }
        if not any(content.strip() for content in resume_sections.values()):
            st.warning("请至少填写一项履历内容。")
        else:
            career_store.save_profile_sections(
                resume_sections,
                source_file=source_file,
                verified=verified,
            )
            st.session_state.reset_profile_draft = True
            set_message("履历内容已保存；既有匹配分析已保留为历史，请重新生成当前结果。")
            refresh_page()
    if evidence_records:
        with st.expander("已保存履历内容"):
            for category, label in PROFILE_CATEGORIES.items():
                category_records = [
                    evidence for evidence in evidence_records if evidence.category == category
                ]
                if category_records:
                    st.markdown(f"**{label}**")
                    for evidence in category_records:
                        content_col, delete_col = st.columns([6, 1])
                        content_col.write(evidence.content)
                        if evidence.source_file:
                            content_col.caption(f"来源：{evidence.source_file}")
                        if delete_col.button("删除", key=f"delete_evidence_{evidence.evidence_id}"):
                            career_store.delete_profile_evidence(evidence.evidence_id)
                            set_message(f"{label}中的一条内容已删除；既有匹配分析已保留为历史。")
                            refresh_page()


@st.fragment
def render_jobs_page() -> None:
    show_message()
    st.subheader("岗位 JD")
    if extraction := st.session_state.pop("job_extraction_prefill", None):
        prefill_extracted_job(extraction)
    st.markdown("**导入岗位文件**")
    job_upload = st.file_uploader(
        "上传 PDF / Markdown / TXT 岗位 JD",
        type=["pdf", "md", "markdown", "txt"],
        key="job_posting_upload",
    )
    if job_upload and st.button("解析并回填岗位草稿"):
        if not assistant.is_configured():
            st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
        else:
            try:
                with st.spinner("正在从文件提取岗位信息..."):
                    extraction = assistant.extract_job_upload(
                        job_upload.name, job_upload.getvalue()
                    )
                st.session_state.job_extraction_prefill = extraction.__dict__
                set_message("岗位文件已解析并回填为草稿，请复核字段后保存岗位。")
                refresh_page()
            except (RuntimeError, ValueError) as exc:
                st.error(f"提取失败：{exc}")
    st.markdown("**编辑岗位草稿**")
    with st.form("job_posting_form"):
        first, second = st.columns(2)
        company = first.text_input("公司", key="new_job_company")
        job_title = second.text_input("岗位名称", key="new_job_title")
        location = first.text_input("地点", key="new_job_location")
        source_url = second.text_input("来源链接", key="new_job_source_url")
        raw_description = st.text_area("JD 原文", height=170, key="new_job_raw_description")
        required_skills_text = st.text_area("必备技能", height=70, key="new_job_required_skills")
        preferred_skills_text = st.text_area("加分技能", height=70, key="new_job_preferred_skills")
        requirements_text = st.text_area("实习条件", height=70, key="new_job_requirements")
        extract_job = st.form_submit_button("从 JD 提取并回填字段")
        save_job = st.form_submit_button("保存岗位", type="primary")
    if extract_job:
        if not raw_description.strip():
            st.warning("请先输入 JD 原文。")
        elif not assistant.is_configured():
            st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
        else:
            try:
                with st.spinner("正在提取岗位要求..."):
                    extraction = assistant.extract_job_posting_text(raw_description)
                st.session_state.job_extraction_prefill = extraction.__dict__
                set_message("岗位信息已提取并回填，请复核字段后保存岗位。")
                refresh_page()
            except (RuntimeError, ValueError) as exc:
                st.error(f"提取失败：{exc}")
    if save_job:
        try:
            career_store.add_job_posting(
                company=company,
                title=job_title,
                location=location,
                source_url=source_url,
                raw_description=raw_description,
                required_skills=parse_items(required_skills_text),
                preferred_skills=parse_items(preferred_skills_text),
                internship_requirements=parse_items(requirements_text),
            )
            clear_job_form()
            set_message("岗位 JD 已保存。")
            refresh_page()
        except ValueError as exc:
            st.error(str(exc))

    jobs = career_store.list_job_postings()
    if not jobs:
        st.info("还没有岗位 JD。")
    for job in reversed(jobs):
        with st.expander(format_job(job)):
            st.write(job.raw_description)
            if job.required_skills:
                st.markdown(f"**必备技能：** {', '.join(job.required_skills)}")
            if job.preferred_skills:
                st.markdown(f"**加分技能：** {', '.join(job.preferred_skills)}")
            if job.internship_requirements:
                st.markdown(f"**实习条件：** {', '.join(job.internship_requirements)}")
            if job.source_url:
                st.link_button("打开来源", job.source_url)
            if st.button("删除岗位", key=f"delete_job_{job.job_id}"):
                career_store.delete_job_posting(job.job_id)
                set_message("岗位及其关联分析、投递记录已删除。")
                refresh_page()


@st.fragment
def render_analysis_page() -> None:
    show_message()
    st.subheader("岗位匹配分析")
    jobs = career_store.list_job_postings()
    evidence_records = career_store.list_profile_evidence()
    evidence_by_id = {evidence.evidence_id: evidence for evidence in evidence_records}
    if not jobs:
        st.info("请先在岗位库保存一个岗位。")
        return
    job_by_id = {job.job_id: job for job in jobs}
    selected_job_id = st.selectbox(
        "选择岗位",
        list(job_by_id),
        format_func=lambda job_id: format_job(job_by_id[job_id]),
        key="analysis_job_id",
    )
    action_one, action_two = st.columns(2)
    if action_one.button("运行关键词基线", type="primary"):
        analysis = career_store.analyze_job_match(selected_job_id)
        set_message(f"关键词匹配基线已生成，当前得分 {analysis.score:.1f}。")
        refresh_page()
    if action_two.button("运行混合分析"):
        verified = [evidence for evidence in evidence_records if evidence.verified]
        if not verified:
            st.error("请先在个人档案中确认至少一条可用于匹配的履历内容。")
        elif not assistant.is_configured():
            st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
        else:
            job = job_by_id[selected_job_id]
            try:
                baseline = career_store.analyze_job_match(selected_job_id)
                keyword_summary = (
                    f"已覆盖必备技能：{', '.join(baseline.matched_requirements) or '暂无'}；"
                    f"缺少必备证据：{', '.join(baseline.missing_requirements) or '暂无'}；"
                    f"已覆盖加分技能：{', '.join(baseline.matched_preferred_skills) or '暂无'}。"
                )
                with st.spinner("正在进行语义匹配与证据解释..."):
                    supplement = assistant.analyze_semantic_match(
                        job_description=job.raw_description,
                        evidence=[(item.evidence_id, item.content) for item in verified],
                        keyword_summary=keyword_summary,
                    )
                analysis = career_store.enhance_match_analysis(
                    baseline.analysis_id,
                    semantic_score=supplement.semantic_score,
                    semantic_evidence_ids=supplement.evidence_ids,
                    model_explanation=supplement.model_explanation,
                )
                set_message(f"混合匹配分析已生成，综合得分 {analysis.score:.1f}。")
                refresh_page()
            except (RuntimeError, ValueError) as exc:
                st.error(f"混合分析失败：{exc}")
    selected_analyses = career_store.list_match_analyses(selected_job_id)
    if selected_analyses:
        show_analysis(selected_analyses[-1], evidence_by_id)
        st.markdown("**该岗位分析历史**")
        st.dataframe(
            [
                {
                    "分析时间": analysis.created_at,
                    "状态": "历史/需重算" if analysis.is_stale else "当前",
                    "分析方式": "混合" if analysis.analysis_type == "hybrid" else "关键词",
                    "匹配分数": analysis.score,
                    "必备缺口": ", ".join(analysis.missing_requirements) or "暂无",
                }
                for analysis in reversed(selected_analyses)
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("该岗位还没有分析结果。")
    latest_by_job = {}
    for analysis in career_store.list_match_analyses():
        latest_by_job[analysis.job_id] = analysis
    if latest_by_job:
        st.subheader("已分析岗位")
        rows = [
            {
                    "岗位": format_job(job_by_id[job_id]),
                    "状态": "历史/需重算" if analysis.is_stale else "当前",
                    "分析方式": "混合" if analysis.analysis_type == "hybrid" else "关键词",
                    "匹配分数": analysis.score,
                "必备缺口": ", ".join(analysis.missing_requirements) or "暂无",
                "分析时间": analysis.created_at,
            }
            for job_id, analysis in latest_by_job.items()
            if job_id in job_by_id
        ]
        st.dataframe(rows, width="stretch", hide_index=True)


@st.fragment
def render_resume_page() -> None:
    show_message()
    st.subheader("简历定制")
    jobs = career_store.list_job_postings()
    verified_evidence = [
        evidence for evidence in career_store.list_profile_evidence() if evidence.verified
    ]
    if not jobs:
        st.info("请先在岗位库保存岗位。")
        return
    job_by_id = {job.job_id: job for job in jobs}
    if not verified_evidence:
        st.info("请先在个人档案中确认至少一条可用于简历的真实经历。")
        show_saved_resume_versions(job_by_id)
        return
    evidence_by_id = {evidence.evidence_id: evidence for evidence in verified_evidence}
    with st.form("resume_tailor_form"):
        selected_job_id = st.selectbox(
            "目标岗位",
            list(job_by_id),
            format_func=lambda job_id: format_job(job_by_id[job_id]),
        )
        selected_evidence_ids = st.multiselect(
            "采用的已确认履历",
            list(evidence_by_id),
            default=list(evidence_by_id),
            format_func=lambda evidence_id: (
                f"{PROFILE_CATEGORIES[evidence_by_id[evidence_id].category]} · "
                f"{evidence_by_id[evidence_id].content[:55]}"
            ),
        )
        current_text = st.text_area("当前简历表述", height=100)
        request = st.text_input("修改目标", placeholder="例如：优化为项目经历中的一条要点")
        generate_resume = st.form_submit_button("生成定制建议", type="primary")
    if generate_resume:
        if not assistant.is_configured():
            st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
        else:
            try:
                with st.spinner("正在生成基于证据的简历建议..."):
                    customization = assistant.tailor_resume(
                        job_description=job_by_id[selected_job_id].raw_description,
                        evidence=[evidence_by_id[item].content for item in selected_evidence_ids],
                        current_text=current_text,
                        request=request,
                    )
                st.session_state.resume_custom_result = {
                    "job_id": selected_job_id,
                    "fit_assessment": customization.fit_assessment,
                    "recommended_text": customization.recommended_text,
                    "evidence_basis": customization.evidence_basis,
                    "gap_notes": customization.gap_notes,
                }
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))

    result = st.session_state.get("resume_custom_result")
    if result:
        job = job_by_id.get(result["job_id"])
        if job:
            st.markdown(f"**目标岗位：** {format_job(job)}")
            if "recommended_text" not in result:
                st.warning("当前为旧格式定制结果，请重新生成后再继续使用。")
            else:
                st.markdown("**推荐表述**")
                st.markdown(result["recommended_text"])
                with st.expander("查看审核信息"):
                    st.markdown("**适配判断**")
                    st.write(result["fit_assessment"] or "暂无")
                    st.markdown("**证据依据**")
                    st.write(result["evidence_basis"] or "暂无")
                    st.markdown("**缺口提示**")
                    st.write(result["gap_notes"] or "暂无")
                st.divider()
                adopt_col, version_col = st.columns(2)
                with adopt_col:
                    st.markdown("**采纳到个人档案**")
                    st.caption("输入框仅带入推荐表述；请核对真实后写入档案。")
                    with st.form("adopt_resume_form"):
                        target_category = st.selectbox(
                            "写入栏目",
                            ["project", "skill", "award", "education"],
                            format_func=lambda category: PROFILE_CATEGORIES[category],
                        )
                        adopted_content = st.text_area(
                            "待写入内容",
                            value=result["recommended_text"],
                            height=140,
                        )
                        confirmed = st.checkbox("我已核对内容真实，可以加入个人档案")
                        adopt_resume = st.form_submit_button("写入个人档案", type="primary")
                    if adopt_resume:
                        if not confirmed:
                            st.warning("请先核对并确认内容真实。")
                        elif not adopted_content.strip():
                            st.warning("请填写需要写入个人档案的内容。")
                        else:
                            career_store.add_profile_evidence(
                                category=target_category,
                                content=adopted_content,
                                source_file=f"简历定制：{format_job(job)}",
                                verified=True,
                            )
                            set_message("已写入个人档案；既有匹配分析已保留为历史，请重新生成当前结果。")
                            refresh_page()
                with version_col:
                    st.markdown("**保存定制版本**")
                    st.caption("版本用于后续投递关联，不会自动改写个人档案。")
                    with st.form("save_resume_version_form"):
                        version_name = st.text_input(
                            "版本名称", value=f"{job.company}-{job.title}-定制版"
                        )
                        version_category = st.selectbox(
                            "表述所属栏目",
                            ["project", "skill", "award", "education"],
                            format_func=lambda category: PROFILE_CATEGORIES[category],
                            key="version_target_category",
                        )
                        version_content = st.text_area(
                            "版本内容", value=result["recommended_text"], height=140
                        )
                        save_version = st.form_submit_button("保存版本", type="primary")
                    if save_version:
                        try:
                            career_store.add_resume_version(
                                job_id=job.job_id,
                                name=version_name,
                                content=version_content,
                                target_category=version_category,
                                fit_assessment=result["fit_assessment"],
                                evidence_basis=result["evidence_basis"],
                                gap_notes=result["gap_notes"],
                            )
                            set_message("定制简历版本已保存，可在投递记录中选择使用。")
                            refresh_page()
                        except ValueError as exc:
                            st.error(str(exc))

    show_saved_resume_versions(job_by_id)


@st.fragment
def render_applications_page() -> None:
    show_message()
    st.subheader("投递记录")
    jobs = career_store.list_job_postings()
    if not jobs:
        st.info("请先在岗位库保存岗位。")
        return
    job_by_id = {job.job_id: job for job in jobs}
    application_job_id = st.selectbox(
        "岗位",
        list(job_by_id),
        format_func=lambda job_id: format_job(job_by_id[job_id]),
        key="new_application_job_id",
    )
    versions_for_job = career_store.list_resume_versions(application_job_id)
    version_by_id = {version.version_id: version for version in versions_for_job}
    with st.form("new_application_form", clear_on_submit=True):
        application_status = st.selectbox(
            "当前状态",
            list(APPLICATION_STATUSES),
            format_func=lambda status: APPLICATION_STATUSES[status],
        )
        selected_version_id = st.selectbox(
            "使用的定制简历版本",
            ["", *list(version_by_id)],
            format_func=lambda version_id: (
                "未关联版本" if not version_id else version_by_id[version_id].name
            ),
        )
        submitted_at = st.text_input("投递时间")
        notes = st.text_area("备注", height=80)
        add_application = st.form_submit_button("新增记录", type="primary")
    if add_application:
        analyses = career_store.list_match_analyses(application_job_id)
        career_store.add_application(
            job_id=application_job_id,
            status=application_status,
            analysis_id=analyses[-1].analysis_id if analyses else "",
            resume_version=version_by_id[selected_version_id].name if selected_version_id else "",
            resume_version_id=selected_version_id,
            submitted_at=submitted_at,
            notes=notes,
        )
        set_message("投递记录已保存。")
        refresh_page()

    applications = career_store.list_applications()
    if not applications:
        st.info("还没有投递记录。")
    for record in reversed(applications):
        job = job_by_id.get(record.job_id)
        if not job:
            continue
        with st.expander(f"{format_job(job)} · {APPLICATION_STATUSES[record.status]}"):
            record_versions = career_store.list_resume_versions(record.job_id)
            record_version_by_id = {version.version_id: version for version in record_versions}
            stored_version_ids = ["", *list(record_version_by_id)]
            current_version_id = (
                record.resume_version_id
                if record.resume_version_id in record_version_by_id
                else ""
            )
            with st.form(f"edit_application_{record.application_id}"):
                edit_status = st.selectbox(
                    "当前状态",
                    list(APPLICATION_STATUSES),
                    index=list(APPLICATION_STATUSES).index(record.status),
                    format_func=lambda status: APPLICATION_STATUSES[status],
                    key=f"status_{record.application_id}",
                )
                edit_version_id = st.selectbox(
                    "使用的定制简历版本",
                    stored_version_ids,
                    index=stored_version_ids.index(current_version_id),
                    format_func=lambda version_id: (
                        "未关联版本"
                        if not version_id
                        else record_version_by_id[version_id].name
                    ),
                    key=f"resume_{record.application_id}",
                )
                edit_submitted = st.text_input(
                    "投递时间", value=record.submitted_at, key=f"time_{record.application_id}"
                )
                edit_notes = st.text_area(
                    "备注", value=record.notes, height=80, key=f"notes_{record.application_id}"
                )
                update_application = st.form_submit_button("保存修改", type="primary")
            if update_application:
                career_store.update_application(
                    record.application_id,
                    status=edit_status,
                    resume_version=(
                        record_version_by_id[edit_version_id].name if edit_version_id else ""
                    ),
                    resume_version_id=edit_version_id,
                    submitted_at=edit_submitted,
                    notes=edit_notes,
                )
                set_message("投递记录已更新。")
                refresh_page()
            if st.button("删除记录", key=f"delete_application_{record.application_id}"):
                career_store.delete_application(record.application_id)
                set_message("投递记录已删除。")
                refresh_page()


@st.fragment
def render_library_page() -> None:
    show_message()
    st.subheader("参考资料库")
    library_page = st.segmented_control(
        "参考资料功能",
        LIBRARY_PAGES,
        default=LIBRARY_PAGES[0],
        key="library_page",
        label_visibility="collapsed",
    ) or LIBRARY_PAGES[0]
    if library_page == "资料管理":
        uploads = st.file_uploader(
            "上传 PDF / Markdown / TXT",
            type=["pdf", "md", "markdown", "txt"],
            accept_multiple_files=True,
        )
        if uploads and st.button("保存上传文件"):
            for upload in uploads:
                assistant.save_upload(upload.name, upload.getvalue())
            set_message(f"已保存 {len(uploads)} 个参考文件。")
            refresh_page()
        if st.button("重建参考资料索引", type="primary"):
            if not assistant.is_configured():
                st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
            else:
                try:
                    with st.spinner("正在重建参考资料索引..."):
                        assistant.reset_index()
                        count = assistant.ingest_all()
                    set_message(f"参考资料索引已写入 {count} 个片段。")
                    refresh_page()
                except Exception as exc:
                    st.error(f"重建索引失败：{exc}")
        files = assistant.list_documents()
        for file in files:
            location = (
                "上传资料"
                if assistant.config.upload_dir.resolve() in file.resolve().parents
                else "本地资料"
            )
            file_col, action_col = st.columns([5, 1])
            file_col.write(f"{file.name} · {location}")
            if action_col.button("删除", key=f"delete_{file.resolve()}"):
                try:
                    assistant.delete_document(file)
                    set_message(sync_index_after_document_change())
                    refresh_page()
                except Exception as exc:
                    st.error(f"删除失败：{exc}")
        uploaded_files = [
            file for file in files if assistant.config.upload_dir.resolve() in file.resolve().parents
        ]
        if uploaded_files and st.button("清空上传资料"):
            removed = assistant.clear_uploads()
            set_message(f"已删除 {removed} 个上传文件。" + sync_index_after_document_change())
            refresh_page()
    elif library_page == "资料问答":
        question = st.text_area(
            "基于参考资料提问",
            height=100,
            placeholder="例如：资料中的项目经历表述应突出哪些信息？",
        )
        if st.button("基于资料回答", type="primary"):
            if not question.strip():
                st.warning("请先输入问题。")
            elif not assistant.is_configured():
                st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
            else:
                with st.spinner("检索参考资料并生成回答..."):
                    st.session_state.library_answer = assistant.ask(
                        question.strip(), top_k=st.session_state.top_k
                    )
        if answer := st.session_state.get("library_answer"):
            st.markdown(answer["answer"])
            for source in answer["sources"]:
                st.caption(f"{source['source']} · chunk {source['chunk_index']}")
                st.write(source["content"])
    elif library_page == "检索调试":
        search_query = st.text_input("检索问题或关键词")
        if st.button("查看召回片段"):
            if not search_query.strip():
                st.warning("请输入检索内容。")
            elif not assistant.is_configured():
                st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
            else:
                with st.spinner("正在检索片段..."):
                    st.session_state.library_search_results = assistant.search(
                        search_query.strip(), top_k=st.session_state.top_k
                    )
        for item in st.session_state.get("library_search_results", []):
            status = "可进入上下文" if item["accepted"] else "低于阈值"
            st.markdown(f"**{item['source']}** · {item['score']:.3f} · {status}")
            st.write(item["content"])
    else:
        if st.button("生成资料摘要"):
            if not assistant.is_configured():
                st.error("请先在 .env 中设置 DASHSCOPE_API_KEY。")
            else:
                with st.spinner("正在生成资料摘要..."):
                    assistant.summarize()
                set_message("资料摘要已生成。")
                refresh_page()
        history = assistant.load_history()
        if history:
            confirm_clear = st.checkbox("确认清空全部摘要与问答历史")
            if st.button("清空全部历史", disabled=not confirm_clear):
                removed = assistant.clear_history()
                set_message(f"已清空 {removed} 条摘要与问答历史。")
                refresh_page()
        else:
            st.info("还没有摘要或资料问答历史。")
        for record in reversed(history):
            with st.expander(f"{record['time']} · {record['question']}"):
                st.markdown(record["answer"])
                for source in record.get("sources", []):
                    st.caption(f"{source.get('source')} · chunk {source.get('chunk_index')}")
                if st.button("删除这条记录", key=f"delete_history_{record['history_id']}"):
                    assistant.delete_history_record(record["history_id"])
                    set_message("该条摘要或问答历史已删除。")
                    refresh_page()


st.title("智能选岗及简历定制 Agent")
active_page = st.segmented_control(
    "功能导航",
    PAGES,
    default=PAGES[0],
    key="active_page",
    label_visibility="collapsed",
) or PAGES[0]

page_renderers = {
    "个人档案": render_profile_page,
    "岗位库": render_jobs_page,
    "匹配分析": render_analysis_page,
    "简历定制": render_resume_page,
    "投递记录": render_applications_page,
    "参考资料库": render_library_page,
}
page_renderers[active_page]()
