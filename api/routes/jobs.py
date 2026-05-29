from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_career_store
from api.models import JobPostingCreate, JobPostingResponse
from career_store import CareerStore

router = APIRouter()


@router.get("/jobs", response_model=list[JobPostingResponse])
def list_jobs(store: CareerStore = Depends(get_career_store)):
    return store.list_job_postings()


@router.post("/jobs", response_model=JobPostingResponse)
def add_job(body: JobPostingCreate, store: CareerStore = Depends(get_career_store)):
    return store.add_job_posting(**body.model_dump())


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_job_posting(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到需要删除的岗位。")
    return {"ok": True}
