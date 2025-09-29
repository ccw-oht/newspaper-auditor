from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import SessionLocal
from ..models import Audit, Paper

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=schemas.PaperListResponse)
def list_papers(
    state: Optional[str] = Query(default=None, description="Filter by state abbreviation"),
    has_pdf: Optional[str] = Query(default=None, description="Filter by Has PDF Edition? result"),
    pdf_only: Optional[str] = Query(default=None, description="Filter by PDF-Only? result"),
    paywall: Optional[str] = Query(default=None, description="Filter by Paywall? result"),
    notices: Optional[str] = Query(default=None, description="Filter by Free Public Notices result"),
    responsive: Optional[str] = Query(default=None, description="Filter by Mobile Responsive result"),
    q: Optional[str] = Query(default=None, description="Search by paper name or city"),
    sort: str = Query(default="paper_name", description="Field to sort by"),
    order: str = Query(default="asc", description="Sort direction (asc/desc)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(default=0, ge=0, description="Records to skip"),
    db: Session = Depends(get_db),
):
    latest_audit_subq = (
        select(
            Audit.id.label("audit_id"),
            Audit.paper_id.label("paper_id"),
            Audit.timestamp.label("timestamp"),
            Audit.has_pdf.label("has_pdf"),
            Audit.pdf_only.label("pdf_only"),
            Audit.paywall.label("paywall"),
            Audit.notices.label("notices"),
            Audit.responsive.label("responsive"),
            Audit.sources.label("sources"),
            Audit.notes.label("notes"),
            func.substr(Audit.homepage_html, 1, 1500).label("homepage_preview"),
            func.row_number()
            .over(partition_by=Audit.paper_id, order_by=Audit.timestamp.desc())
            .label("row_number"),
        )
    ).subquery()

    latest = latest_audit_subq.alias("latest")

    stmt = (
        select(Paper, latest)
        .outerjoin(latest, (Paper.id == latest.c.paper_id) & (latest.c.row_number == 1))
    )

    conditions = []

    if state:
        conditions.append(Paper.state == state.strip())

    def _normalize_filter(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    audit_filters = {
        "has_pdf": has_pdf,
        "pdf_only": pdf_only,
        "paywall": paywall,
        "notices": notices,
        "responsive": responsive,
    }

    for column_name, raw_value in audit_filters.items():
        normalized = _normalize_filter(raw_value)
        if normalized:
            column = getattr(latest.c, column_name)
            conditions.append(func.lower(column) == normalized.lower())

    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                Paper.paper_name.ilike(pattern),
                Paper.city.ilike(pattern),
                Paper.state.ilike(pattern),
            )
        )

    if conditions:
        stmt = stmt.where(*conditions)

    sortable_columns = {
        "paper_name": Paper.paper_name,
        "city": Paper.city,
        "state": Paper.state,
        "timestamp": latest.c.timestamp,
    }

    sort_key = sortable_columns.get(sort.lower(), Paper.paper_name)
    sort_order = order.lower()
    if sort_order == "desc":
        order_clause = desc(sort_key).nulls_last()
    else:
        order_clause = asc(sort_key).nulls_last()

    stmt = stmt.order_by(order_clause).offset(offset).limit(limit)

    rows = db.execute(stmt).all()

    items: list[schemas.PaperSummary] = []
    for paper, latest_row in rows:
        latest_audit = None
        if latest_row and latest_row["audit_id"] is not None:
            latest_audit = schemas.AuditSummary(
                id=latest_row["audit_id"],
                timestamp=latest_row["timestamp"],
                has_pdf=latest_row["has_pdf"],
                pdf_only=latest_row["pdf_only"],
                paywall=latest_row["paywall"],
                notices=latest_row["notices"],
                responsive=latest_row["responsive"],
                sources=latest_row["sources"],
                notes=latest_row["notes"],
                homepage_preview=latest_row["homepage_preview"],
            )

        items.append(
            schemas.PaperSummary(
                id=paper.id,
                state=paper.state,
                city=paper.city,
                paper_name=paper.paper_name,
                website_url=paper.website_url,
                phone=paper.phone,
                mailing_address=paper.mailing_address,
                county=paper.county,
                extra_data=paper.extra_data,
                latest_audit=latest_audit,
            )
        )

    count_join = Paper.__table__.outerjoin(
        latest,
        (Paper.id == latest.c.paper_id) & (latest.c.row_number == 1),
    )
    count_stmt = select(func.count()).select_from(count_join)
    if conditions:
        count_stmt = count_stmt.where(*conditions)

    total = db.execute(count_stmt).scalar_one()

    return schemas.PaperListResponse(total=total, items=items)


@router.get("/{paper_id}", response_model=schemas.PaperDetail)
def retrieve_paper(paper_id: int, db: Session = Depends(get_db)):
    return _fetch_paper_detail(db, paper_id)


@router.patch("/{paper_id}", response_model=schemas.PaperDetail)
def update_paper(
    paper_id: int,
    payload: schemas.PaperUpdate,
    db: Session = Depends(get_db),
):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    updates = payload.dict(exclude_unset=True)

    def _clean_str(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    for field in [
        "state",
        "city",
        "paper_name",
        "website_url",
        "phone",
        "mailing_address",
        "county",
    ]:
        if field in updates:
            setattr(paper, field, _clean_str(updates[field]))

    if "extra_data" in updates:
        extra_value = updates["extra_data"]
        if extra_value is None:
            paper.extra_data = None
        else:
            paper.extra_data = {**(paper.extra_data or {}), **extra_value}

    db.add(paper)
    db.commit()

    return _fetch_paper_detail(db, paper_id)


def _fetch_paper_detail(db: Session, paper_id: int) -> schemas.PaperDetail:
    stmt = (
        select(Paper)
        .options(selectinload(Paper.audits))
        .where(Paper.id == paper_id)
    )
    paper = db.execute(stmt).scalars().first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    audits = sorted(
        paper.audits,
        key=lambda audit: audit.timestamp or datetime.min,
        reverse=True,
    )

    latest = audits[0] if audits else None
    latest_summary = (
        schemas.AuditSummary(
            id=latest.id,
            timestamp=latest.timestamp,
            has_pdf=latest.has_pdf,
            pdf_only=latest.pdf_only,
            paywall=latest.paywall,
            notices=latest.notices,
            responsive=latest.responsive,
            sources=latest.sources,
            notes=latest.notes,
            homepage_preview=(latest.homepage_html[:1500] if latest.homepage_html else None),
        )
        if latest
        else None
    )

    audit_history = [schemas.AuditOut.from_orm(audit) for audit in audits]

    return schemas.PaperDetail(
        id=paper.id,
        state=paper.state,
        city=paper.city,
        paper_name=paper.paper_name,
        website_url=paper.website_url,
        phone=paper.phone,
        mailing_address=paper.mailing_address,
        county=paper.county,
        extra_data=paper.extra_data,
        latest_audit=latest_summary,
        audits=audit_history,
    )
