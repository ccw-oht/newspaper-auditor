from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..models import Audit, Paper
from ..services import audit_service

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        audit, results, _error_note = audit_service.perform_audit(db, paper)
        audits.append(audit)

    db.commit()
    for audit in audits:
        db.refresh(audit)

    return audits


@router.delete("/{paper_id}", status_code=204)
def clear_audit_results(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    db.execute(delete(Audit).where(Audit.paper_id == paper_id))
    paper.chain_owner = None
    paper.cms_platform = None
    paper.cms_vendor = None
    extra = dict(paper.extra_data or {})
    job_status = extra.get("job_status")
    if isinstance(job_status, dict) and "audit" in job_status:
        job_status = dict(job_status)
        job_status.pop("audit", None)
        if job_status:
            extra["job_status"] = job_status
        else:
            extra.pop("job_status", None)
        paper.extra_data = extra
    db.commit()
    return Response(status_code=204)


@router.post("/{paper_id}", response_model=schemas.AuditOut)
def audit_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    audit, _results, _error_note = audit_service.perform_audit(db, paper)
    return audit
