from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..models import Paper
from ..services import lookup_service

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{paper_id}", response_model=schemas.LookupResult)
def lookup_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    try:
        return lookup_service.lookup_paper_contact(db, paper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/batch", response_model=list[schemas.LookupResult])
def lookup_batch(payload: schemas.LookupBatchRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    results: list[schemas.LookupResult] = []
    for paper_id in payload.ids:
        paper = db.get(Paper, paper_id)
        if not paper:
            results.append(
                schemas.LookupResult(
                    paper_id=paper_id,
                    updated=False,
                    error="Paper not found",
                )
            )
            continue
        try:
            results.append(lookup_service.lookup_paper_contact(db, paper))
        except Exception as exc:
            results.append(
                schemas.LookupResult(
                    paper_id=paper_id,
                    updated=False,
                    error=str(exc),
                )
            )
    return results
