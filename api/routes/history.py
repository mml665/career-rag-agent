from fastapi import APIRouter, Depends

from api.deps import get_rag_assistant
from rag_agent import RagAssistant

router = APIRouter()


@router.get("/library/history")
def list_history(limit: int | None = None, assistant: RagAssistant = Depends(get_rag_assistant)):
    return assistant.load_history(limit)


@router.delete("/library/history/{history_id}")
def delete_history(history_id: str, assistant: RagAssistant = Depends(get_rag_assistant)):
    assistant.delete_history_record(history_id)
    return {"ok": True}


@router.delete("/library/history")
def clear_history(assistant: RagAssistant = Depends(get_rag_assistant)):
    assistant.clear_history()
    return {"ok": True}
