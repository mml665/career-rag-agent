from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_career_store
from api.models import (
    ProfileEvidenceCreate,
    ProfileEvidenceResponse,
    ProfileEvidenceUpdate,
    ProfileSectionsRequest,
)
from career_store import CareerStore

router = APIRouter()


@router.get("/evidence", response_model=list[ProfileEvidenceResponse])
def list_evidence(store: CareerStore = Depends(get_career_store)):
    return store.list_profile_evidence()


@router.post("/evidence", response_model=ProfileEvidenceResponse)
def add_evidence(body: ProfileEvidenceCreate, store: CareerStore = Depends(get_career_store)):
    return store.add_profile_evidence(**body.model_dump())


@router.put("/evidence/{evidence_id}", response_model=ProfileEvidenceResponse)
def update_evidence(
    evidence_id: str,
    body: ProfileEvidenceUpdate,
    store: CareerStore = Depends(get_career_store),
):
    return store.update_profile_evidence(evidence_id, **body.model_dump())


@router.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_profile_evidence(evidence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到需要删除的履历证据。")
    return {"ok": True}


@router.post("/evidence/sections", response_model=list[ProfileEvidenceResponse])
def save_sections(body: ProfileSectionsRequest, store: CareerStore = Depends(get_career_store)):
    return store.save_profile_sections(
        body.sections, source_file=body.source_file, verified=body.verified
    )


@router.delete("/evidence/section/{category}")
def delete_section(category: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_profile_section(category)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到该类别的履历证据。")
    return {"ok": True}
