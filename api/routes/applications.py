from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_career_store
from api.models import (
    ApplicationRecordCreate,
    ApplicationRecordResponse,
    ApplicationRecordUpdate,
)
from career_store import CareerStore

router = APIRouter()


@router.get("/applications", response_model=list[ApplicationRecordResponse])
def list_applications(store: CareerStore = Depends(get_career_store)):
    return store.list_applications()


@router.post("/applications", response_model=ApplicationRecordResponse)
def add_application(
    body: ApplicationRecordCreate, store: CareerStore = Depends(get_career_store)
):
    return store.add_application(**body.model_dump())


@router.put("/applications/{application_id}", response_model=ApplicationRecordResponse)
def update_application(
    application_id: str,
    body: ApplicationRecordUpdate,
    store: CareerStore = Depends(get_career_store),
):
    return store.update_application(application_id, **body.model_dump())


@router.delete("/applications/{application_id}")
def delete_application(application_id: str, store: CareerStore = Depends(get_career_store)):
    deleted = store.delete_application(application_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到需要删除的投递记录。")
    return {"ok": True}
