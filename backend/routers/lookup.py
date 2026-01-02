from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..models import Paper
from ..services import lookup_service

router = APIRouter()
_LOOKUP_BATCH_CONCURRENCY = int(os.getenv("LOOKUP_BATCH_CONCURRENCY", "5"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/batch", response_model=list[schemas.LookupResult])
def lookup_batch(payload: schemas.LookupBatchRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    def _lookup_one(paper_id: int) -> schemas.LookupResult:
        local_db = SessionLocal()
        try:
            paper = local_db.get(Paper, paper_id)
            if not paper:
                return schemas.LookupResult(
                    paper_id=paper_id,
                    updated=False,
                    error="Paper not found",
                )
            return lookup_service.lookup_paper_contact(local_db, paper)
        except Exception as exc:
            return schemas.LookupResult(
                paper_id=paper_id,
                updated=False,
                error=str(exc),
            )
        finally:
            local_db.close()

    max_workers = max(1, min(_LOOKUP_BATCH_CONCURRENCY, len(payload.ids)))
    if max_workers == 1:
        return [_lookup_one(paper_id) for paper_id in payload.ids]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_lookup_one, payload.ids))


@router.post("/{paper_id}", response_model=schemas.LookupResult)
def lookup_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    try:
        return lookup_service.lookup_paper_contact(db, paper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
