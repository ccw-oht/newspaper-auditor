from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..services import import_service


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/preview", response_model=schemas.ImportPreviewResponse)
async def preview_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:  # pragma: no cover - pandas-specific errors
        raise HTTPException(status_code=400, detail=f"Unable to parse CSV: {exc}") from exc

    staged_rows, summary_counts = import_service.generate_preview(df, db)

    rows: list[schemas.ImportPreviewRow] = []
    for staged in staged_rows:
        rows.append(
            schemas.ImportPreviewRow(
                temp_id=staged.temp_id,
                status=staged.status,
                allowed_actions=import_service.allowed_actions(staged.status),
                data=staged.data,
                existing=_paper_to_dict(staged.existing) if staged.existing else None,
                differences=staged.differences,
                issues=staged.issues,
            )
        )

    summary = schemas.ImportPreviewSummary(**summary_counts)
    return schemas.ImportPreviewResponse(rows=rows, summary=summary)


@router.post("/commit", response_model=schemas.ImportCommitResult)
def commit_import(payload: schemas.ImportCommitRequest, db: Session = Depends(get_db)):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="No rows provided")

    try:
        result = import_service.commit_rows(db, payload.rows)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


def _paper_to_dict(paper) -> dict:
    return {
        "id": paper.id,
        "state": paper.state,
        "city": paper.city,
        "paper_name": paper.paper_name,
        "website_url": paper.website_url,
        "phone": paper.phone,
        "mailing_address": paper.mailing_address,
        "county": paper.county,
        "extra_data": paper.extra_data or {},
    }
