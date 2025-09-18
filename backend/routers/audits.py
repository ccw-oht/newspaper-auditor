from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Paper, Audit
from audit import run_audit
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{paper_id}")
def audit_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).get(paper_id)
    if not paper:
        return {"error": "Paper not found"}

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
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit

@router.post("/batch")
def audit_batch(ids: list[int], db: Session = Depends(get_db)):
    papers = db.query(Paper).filter(Paper.id.in_(ids)).all()
    audits = []
    for paper in papers:
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
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        audits.append(audit)
    db.commit()
    return audits
