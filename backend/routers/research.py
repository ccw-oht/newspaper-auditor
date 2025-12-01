from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..services import research_service

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class FeatureRunRequest(BaseModel):
    feature_ids: Optional[list[int]] = None


@router.get("/sessions", response_model=schemas.ResearchSessionListResponse)
def list_sessions(db: Session = Depends(get_db)):
    items = research_service.list_research_sessions(db)
    return schemas.ResearchSessionListResponse(items=items)


@router.post("/sessions", response_model=schemas.ResearchSessionDetail)
def create_session(payload: schemas.ResearchSessionCreateRequest, db: Session = Depends(get_db)):
    try:
        session = research_service.create_research_session(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return research_service.get_research_session(db, session.id)


@router.get("/sessions/{session_id}", response_model=schemas.ResearchSessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db)):
    try:
        return research_service.get_research_session(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/sessions/{session_id}/run", response_model=schemas.ResearchFeatureRunListResponse)
def run_session_features(session_id: int, payload: FeatureRunRequest | None = None, db: Session = Depends(get_db)):
    try:
        features = research_service.run_feature_scans(db, session_id, payload.feature_ids if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.ResearchFeatureRunListResponse(features=features)

