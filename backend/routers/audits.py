from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..audit import run_audit
from ..database import SessionLocal
from ..models import Paper, Audit

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{paper_id}", response_model=schemas.AuditOut)
def audit_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    results = run_audit(paper.website_url)

    audit = Audit(
        paper_id=paper.id,
        has_pdf=results["Has PDF Edition?"],
        pdf_only=results["PDF-Only?"],
        paywall=results["Paywall?"],
        notices=results["Free Public Notices?"],
        responsive=results["Mobile Responsive?"],
        sources=results["Audit Sources"],
        notes=results["Audit Notes"],
        homepage_html=results.get("Homepage HTML"),
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


@router.post("/batch", response_model=list[schemas.AuditOut])
def audit_batch(payload: schemas.AuditBatchRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        return []

    papers: dict[int, Paper] = {}
    missing_ids: list[int] = []
    for paper_id in payload.ids:
        paper = db.get(Paper, paper_id)
        if paper is None:
            missing_ids.append(paper_id)
        else:
            papers[paper_id] = paper

    if missing_ids:
        detail = f"Paper IDs not found: {', '.join(map(str, missing_ids))}"
        raise HTTPException(status_code=404, detail=detail)

    audits: list[Audit] = []
    for paper_id in payload.ids:
        paper = papers[paper_id]
        results = run_audit(paper.website_url)
        audit = Audit(
            paper_id=paper.id,
            has_pdf=results["Has PDF Edition?"],
            pdf_only=results["PDF-Only?"],
            paywall=results["Paywall?"],
            notices=results["Free Public Notices?"],
            responsive=results["Mobile Responsive?"],
            sources=results["Audit Sources"],
            notes=results["Audit Notes"],
            homepage_html=results.get("Homepage HTML"),
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        audits.append(audit)

    db.commit()
    for audit in audits:
        db.refresh(audit)

    return audits
