from fastapi import APIRouter, Depends

from api.deps import get_career_store
from api.models import CandidateProfileCreate, CandidateProfileResponse
from career_store import CareerStore

router = APIRouter()


@router.get("/profile", response_model=CandidateProfileResponse)
def get_profile(store: CareerStore = Depends(get_career_store)):
    return store.load_candidate_profile()


@router.post("/profile", response_model=CandidateProfileResponse)
def save_profile(body: CandidateProfileCreate, store: CareerStore = Depends(get_career_store)):
    return store.save_candidate_profile(**body.model_dump())
