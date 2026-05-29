import asyncio

from fastapi import APIRouter, Depends, UploadFile

from api.deps import get_career_store, get_rag_assistant
from api.models import (
    AgentRequest,
    AgentResponse,
    AgentStepResponse,
    AskRequest,
    SearchRequest,
    TailorResumeRequest,
)
from career_store import CareerStore
from rag_agent import RagAssistant

router = APIRouter()


@router.get("/library/configured")
def is_configured(assistant: RagAssistant = Depends(get_rag_assistant)):
    return {"configured": assistant.is_configured()}


@router.get("/library/upload-dir")
def get_upload_dir(assistant: RagAssistant = Depends(get_rag_assistant)):
    return {"upload_dir": str(assistant.config.upload_dir.resolve())}


@router.post("/library/ask")
async def ask(body: AskRequest, assistant: RagAssistant = Depends(get_rag_assistant)):
    result = await asyncio.to_thread(assistant.ask, body.question, body.top_k)
    return result


@router.get("/library/search")
async def search(
    question: str, top_k: int = 5, assistant: RagAssistant = Depends(get_rag_assistant)
):
    results = await asyncio.to_thread(assistant.search, question, top_k)
    return results


@router.post("/library/index")
async def index(body: dict, assistant: RagAssistant = Depends(get_rag_assistant)):
    import copy

    # 创建 config 副本进行临时覆盖，避免并发请求互相污染
    config_override = copy.deepcopy(assistant.config)
    for key in ("enable_bm25", "bm25_weight", "vector_weight", "rrf_k", "enable_rerank", "rerank_top_n"):
        if key in body:
            setattr(config_override, key, body[key])

    original_config = assistant.config
    assistant.config = config_override
    try:
        count = await asyncio.to_thread(assistant.ingest_all)
    finally:
        assistant.config = original_config

    return {"count": count}


@router.post("/library/upload")
async def upload(file: UploadFile, assistant: RagAssistant = Depends(get_rag_assistant)):
    content = await file.read()
    assistant.save_upload(file.filename, content)
    return {"ok": True}


@router.get("/library/documents")
def list_documents(assistant: RagAssistant = Depends(get_rag_assistant)):
    return [
        {
            "name": path.name,
            "path": str(path),
            "size": path.stat().st_size,
        }
        for path in assistant.list_documents()
    ]


@router.delete("/library/documents/{path:path}")
def delete_document(path: str, assistant: RagAssistant = Depends(get_rag_assistant)):
    assistant.delete_document(path)
    return {"ok": True}


@router.delete("/library/documents")
def clear_documents(assistant: RagAssistant = Depends(get_rag_assistant)):
    assistant.clear_uploads()
    assistant.reset_index()
    return {"ok": True}


@router.post("/library/summarize")
async def summarize(assistant: RagAssistant = Depends(get_rag_assistant)):
    result = await asyncio.to_thread(assistant.summarize)
    return result


@router.post("/library/extract-resume")
async def extract_resume(
    file: UploadFile, assistant: RagAssistant = Depends(get_rag_assistant)
):
    content = await file.read()
    result = await asyncio.to_thread(
        assistant.extract_resume_upload, file.filename, content
    )
    return result


@router.post("/library/extract-job-text")
async def extract_job_text(body: dict, assistant: RagAssistant = Depends(get_rag_assistant)):
    raw = body.get("raw_description", "")
    result = await asyncio.to_thread(assistant.extract_job_posting_text, raw)
    return result


@router.post("/library/extract-job-file")
async def extract_job_file(
    file: UploadFile, assistant: RagAssistant = Depends(get_rag_assistant)
):
    content = await file.read()
    result = await asyncio.to_thread(
        assistant.extract_job_upload, file.filename, content
    )
    return result


@router.post("/library/semantic-match")
async def semantic_match(
    body: dict, assistant: RagAssistant = Depends(get_rag_assistant)
):
    evidence = [(item[0], item[1]) for item in body.get("evidence", [])]
    result = await asyncio.to_thread(
        assistant.analyze_semantic_match,
        job_description=body.get("job_description", ""),
        evidence=evidence,
        keyword_summary=body.get("keyword_summary", ""),
    )
    return result


@router.post("/library/tailor-resume")
async def tailor_resume(
    body: dict,
    assistant: RagAssistant = Depends(get_rag_assistant),
):
    result = await asyncio.to_thread(
        assistant.tailor_resume,
        job_description=body.get("job_description", ""),
        evidence=body.get("evidence", []),
        current_text=body.get("current_text", ""),
        request=body.get("request", ""),
    )
    return result


@router.post("/library/export-resume")
async def export_resume(
    body: dict,
    assistant: RagAssistant = Depends(get_rag_assistant),
    store: CareerStore = Depends(get_career_store),
):
    from fastapi.responses import Response
    from resume_export import export_docx, export_pdf

    fmt = body.get("format", "docx")
    profile = store.load_candidate_profile()
    evidence = store.list_profile_evidence()
    content = (body.get("content") or "").strip()
    target_category = body.get("target_category") or "project"
    if content:
        evidence = [
            {
                "category": target_category,
                "title": body.get("name", "定制简历版本"),
                "content": content,
            }
        ]

    try:
        if fmt == "pdf":
            content = await asyncio.to_thread(export_pdf, profile, evidence)
            return Response(
                content=content,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=resume.pdf"},
            )
        else:
            content = await asyncio.to_thread(export_docx, profile, evidence)
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": "attachment; filename=resume.docx"},
            )
    except RuntimeError as e:
        raise
    except Exception as e:
        raise RuntimeError(f"简历导出失败: {e}")


@router.post("/library/agent")
async def agent_chat(
    body: AgentRequest,
    assistant: RagAssistant = Depends(get_rag_assistant),
    store: CareerStore = Depends(get_career_store),
):
    from agent import CareerAgent

    try:
        career_agent = CareerAgent(assistant, store)
        result = await asyncio.to_thread(
            career_agent.run,
            body.message,
            body.max_iterations,
        )
    except Exception as e:
        return AgentResponse(
            answer=f"智能助手初始化失败: {e}",
            steps=[],
            success=False,
            error=str(e),
        )

    return AgentResponse(
        answer=result.answer,
        steps=[
            AgentStepResponse(
                tool_name=step.tool_name,
                tool_input=step.tool_input,
                tool_output=step.tool_output,
            )
            for step in result.steps
        ],
        success=result.success,
        error=result.error,
    )
