from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import schemas
from ..audit import HomepageFetchTimeoutError, run_audit
from ..database import SessionLocal
from ..models import Paper, Audit

router = APIRouter()


def _should_update_metadata(current: str | None, new_value: str | None) -> bool:
    if new_value is None:
        return False
    new_clean = new_value.strip()
    if not new_clean:
        return False

    if current is None:
        return True

    current_clean = current.strip()
    if not current_clean:
        return True

    if current_clean.lower().startswith("manual review"):
        return True

    return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_metadata_updates(paper: Paper, results: dict[str, str | None]) -> None:
    field_map = {
        "chain_owner": "Chain Owner",
        "cms_platform": "CMS Platform",
        "cms_vendor": "CMS Vendor",
    }

    for attr, result_key in field_map.items():
        value = results.get(result_key)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                value = None
        current = getattr(paper, attr)
        if attr == "chain_owner" and value and value.lower() == "independent":
            if isinstance(current, str) and current.strip():
                continue
        if _should_update_metadata(current, value):
            setattr(paper, attr, value)


def _run_audit_or_timeout(paper: Paper) -> tuple[dict[str, str | None] | None, str | None]:
    try:
        return run_audit(paper.website_url), None
    except HomepageFetchTimeoutError as exc:
        safe_url = paper.website_url or "No website URL"
        detail = f"Homepage fetch timed out for paper {paper.id} ({safe_url}): {exc.detail}"
        return None, detail

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
        results, error_note = _run_audit_or_timeout(paper)
        if results:
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
                chain_owner=results.get("Chain Owner"),
                cms_platform=results.get("CMS Platform"),
                cms_vendor=results.get("CMS Vendor"),
                timestamp=datetime.utcnow()
            )
        else:
            audit = Audit(
                paper_id=paper.id,
                notes=error_note,
                timestamp=datetime.utcnow()
            )
        db.add(audit)
        audits.append(audit)
        if results:
            _apply_metadata_updates(paper, results)

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
    db.commit()
    return Response(status_code=204)


@router.post("/{paper_id}", response_model=schemas.AuditOut)
def audit_one(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    results, error_note = _run_audit_or_timeout(paper)

    if results:
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
            chain_owner=results.get("Chain Owner"),
            cms_platform=results.get("CMS Platform"),
            cms_vendor=results.get("CMS Vendor"),
            timestamp=datetime.utcnow()
        )
    else:
        audit = Audit(
            paper_id=paper.id,
            notes=error_note,
            timestamp=datetime.utcnow()
        )
    db.add(audit)
    if results:
        _apply_metadata_updates(paper, results)
    db.commit()
    db.refresh(audit)
    return audit
