from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_career_store
from api.models import ResumeVersionCreate, ResumeVersionResponse
from career_store import CareerStore

router = APIRouter()


@router.get("/resume-versions", response_model=list[ResumeVersionResponse])
def list_versions(job_id: str | None = None, store: CareerStore = Depends(get_career_store)):
    return store.list_resume_versions(job_id)


@router.post("/resume-versions", response_model=ResumeVersionResponse)
def add_version(body: ResumeVersionCreate, store: CareerStore = Depends(get_career_store)):
    return store.add_resume_version(**body.model_dump())


@router.delete("/resume-versions/{version_id}")
def delete_version(version_id: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_resume_version(version_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到需要删除的简历版本。")
    return {"ok": True}
