from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_career_store
from api.models import MatchAnalysisEnhance, MatchAnalysisResponse
from career_store import CareerStore

router = APIRouter()


@router.get("/analyses", response_model=list[MatchAnalysisResponse])
def list_analyses(job_id: str | None = None, store: CareerStore = Depends(get_career_store)):
    return store.list_match_analyses(job_id)


@router.post("/analyses", response_model=MatchAnalysisResponse)
def analyze_match(job_id: str, store: CareerStore = Depends(get_career_store)):
    return store.analyze_job_match(job_id)


@router.put("/analyses/{analysis_id}", response_model=MatchAnalysisResponse)
def enhance_analysis(
    analysis_id: str,
    body: MatchAnalysisEnhance,
    store: CareerStore = Depends(get_career_store),
):
    return store.enhance_match_analysis(analysis_id, **body.model_dump())


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_match_analysis(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到需要删除的匹配分析。")
    return {"ok": True}
