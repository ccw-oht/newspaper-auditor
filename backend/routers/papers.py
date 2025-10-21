import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import SessionLocal
from ..models import Audit, Paper

MISSING_OPTION_LABEL = "(Missing)"

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None

@router.get("/", response_model=schemas.PaperListResponse)
def list_papers(
    state: Optional[str] = Query(default=None, description="Filter by state abbreviation"),
    city: Optional[str] = Query(default=None, description="Filter by city name"),
    has_pdf: Optional[str] = Query(default=None, description="Filter by Has PDF Edition? result"),
    pdf_only: Optional[str] = Query(default=None, description="Filter by PDF-Only? result"),
    paywall: Optional[str] = Query(default=None, description="Filter by Paywall? result"),
    notices: Optional[str] = Query(default=None, description="Filter by Free Public Notices result"),
    responsive: Optional[str] = Query(default=None, description="Filter by Mobile Responsive result"),
    chain_owner: Optional[str] = Query(default=None, description="Filter by detected chain/owner"),
    cms_platform: Optional[str] = Query(default=None, description="Filter by detected CMS platform"),
    cms_vendor: Optional[str] = Query(default=None, description="Filter by detected CMS vendor"),
    q: Optional[str] = Query(default=None, description="Search by paper name or city"),
    sort: str = Query(default="paper_name", description="Field to sort by"),
    order: str = Query(default="asc", description="Sort direction (asc/desc)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(default=0, ge=0, description="Records to skip"),
    db: Session = Depends(get_db),
):
    state_clean = state.strip() if state else None
    city_clean = city.strip() if city else None

    state_stmt = select(func.distinct(Paper.state)).where(Paper.state.isnot(None))
    state_options = sorted(
        {
            value.strip()
            for value, in db.execute(state_stmt)
            if isinstance(value, str) and value.strip()
        }
    )

    city_stmt = select(func.distinct(Paper.city)).where(Paper.city.isnot(None))
    if state_clean:
        city_stmt = city_stmt.where(Paper.state == state_clean)
    city_options = sorted(
        {
            value.strip()
            for value, in db.execute(city_stmt)
            if isinstance(value, str) and value.strip()
        }
    )

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
            Audit.chain_owner.label("chain_owner"),
            Audit.cms_platform.label("cms_platform"),
            Audit.cms_vendor.label("cms_vendor"),
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

    if state_clean:
        conditions.append(Paper.state == state_clean)

    if city_clean:
        conditions.append(Paper.city == city_clean)

    audit_filters = {
        "has_pdf": has_pdf,
        "pdf_only": pdf_only,
        "paywall": paywall,
        "notices": notices,
        "responsive": responsive,
        "chain_owner": chain_owner,
        "cms_platform": cms_platform,
        "cms_vendor": cms_vendor,
    }

    for column_name, raw_value in audit_filters.items():
        column = getattr(latest.c, column_name)
        normalized = _normalize_filter(raw_value)
        condition = _build_audit_condition(column, normalized)
        if condition is not None:
            conditions.append(condition)

    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                Paper.paper_name.ilike(pattern),
                Paper.city.ilike(pattern),
                Paper.state.ilike(pattern),
                Paper.county.ilike(pattern),
                Paper.website_url.ilike(pattern),
                Paper.phone.ilike(pattern),
                latest.c.chain_owner.ilike(pattern),
                latest.c.cms_platform.ilike(pattern),
                latest.c.cms_vendor.ilike(pattern),
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
    for row in rows:
        mapping = row._mapping  # SQLAlchemy RowMapping
        paper: Paper = mapping[Paper]

        audit_id = mapping.get("audit_id")
        latest_audit = None
        if audit_id is not None:
            latest_audit = schemas.AuditSummary(
                id=audit_id,
                timestamp=mapping.get("timestamp"),
                has_pdf=mapping.get("has_pdf"),
                pdf_only=mapping.get("pdf_only"),
                paywall=mapping.get("paywall"),
                notices=mapping.get("notices"),
                responsive=mapping.get("responsive"),
                sources=mapping.get("sources"),
                notes=mapping.get("notes"),
                homepage_preview=mapping.get("homepage_preview"),
                chain_owner=mapping.get("chain_owner"),
                cms_platform=mapping.get("cms_platform"),
                cms_vendor=mapping.get("cms_vendor"),
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

    def _distinct_options(column) -> list[str]:
        option_stmt = select(func.distinct(column)).select_from(count_join)
        if conditions:
            option_stmt = option_stmt.where(*conditions)
        raw_values = [value for value, in db.execute(option_stmt)]
        normalized: set[str] = set()
        include_manual_review = False
        include_missing = False
        for value in raw_values:
            if value is None:
                include_missing = True
                continue
            if not isinstance(value, str):
                include_missing = True
                continue
            stripped = value.strip()
            if not stripped:
                include_missing = True
                continue
            if stripped.lower().startswith("manual review"):
                include_manual_review = True
                continue
            normalized.add(stripped)
        options_list = sorted(normalized)
        if include_manual_review:
            options_list.append("Manual Review")
        if include_missing:
            options_list.append(MISSING_OPTION_LABEL)
        return options_list

    options = schemas.PaperListOptions(
        states=state_options,
        cities=city_options,
        chainOwners=_distinct_options(latest.c.chain_owner),
        cmsPlatforms=_distinct_options(latest.c.cms_platform),
        cmsVendors=_distinct_options(latest.c.cms_vendor),
    )

    return schemas.PaperListResponse(total=total, items=items, options=options)


@router.get("/ids", response_model=schemas.PaperIdList)
def list_paper_ids(
    state: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    has_pdf: Optional[str] = Query(default=None),
    pdf_only: Optional[str] = Query(default=None),
    paywall: Optional[str] = Query(default=None),
    notices: Optional[str] = Query(default=None),
    responsive: Optional[str] = Query(default=None),
    chain_owner: Optional[str] = Query(default=None),
    cms_platform: Optional[str] = Query(default=None),
    cms_vendor: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    state_clean = state.strip() if state else None
    city_clean = city.strip() if city else None

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
            Audit.chain_owner.label("chain_owner"),
            Audit.cms_platform.label("cms_platform"),
            Audit.cms_vendor.label("cms_vendor"),
            func.row_number()
            .over(partition_by=Audit.paper_id, order_by=Audit.timestamp.desc())
            .label("row_number"),
        )
    ).subquery()

    latest = latest_audit_subq.alias("latest")

    stmt = select(Paper.id).outerjoin(latest, (Paper.id == latest.c.paper_id) & (latest.c.row_number == 1))

    conditions = []

    if state_clean:
        conditions.append(Paper.state == state_clean)

    if city_clean:
        conditions.append(Paper.city == city_clean)

    audit_filters = {
        "has_pdf": has_pdf,
        "pdf_only": pdf_only,
        "paywall": paywall,
        "notices": notices,
        "responsive": responsive,
        "chain_owner": chain_owner,
        "cms_platform": cms_platform,
        "cms_vendor": cms_vendor,
    }

    for column_name, raw_value in audit_filters.items():
        column = getattr(latest.c, column_name)
        normalized = _normalize_filter(raw_value)
        condition = _build_audit_condition(column, normalized)
        if condition is not None:
            conditions.append(condition)

    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                Paper.paper_name.ilike(pattern),
                Paper.city.ilike(pattern),
                Paper.state.ilike(pattern),
                Paper.county.ilike(pattern),
                Paper.website_url.ilike(pattern),
                Paper.phone.ilike(pattern),
                latest.c.chain_owner.ilike(pattern),
                latest.c.cms_platform.ilike(pattern),
                latest.c.cms_vendor.ilike(pattern),
            )
        )

    if conditions:
        stmt = stmt.where(*conditions)

    stmt = stmt.order_by(Paper.id)

    ids = [row[0] for row in db.execute(stmt)]
    return schemas.PaperIdList(total=len(ids), ids=ids)


@router.post("/export")
def export_papers(payload: schemas.ExportRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

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
            Audit.chain_owner.label("chain_owner"),
            Audit.cms_platform.label("cms_platform"),
            Audit.cms_vendor.label("cms_vendor"),
            func.row_number()
            .over(partition_by=Audit.paper_id, order_by=Audit.timestamp.desc())
            .label("row_number"),
        )
    ).subquery()

    latest = latest_audit_subq.alias("latest")

    stmt = (
        select(Paper, latest)
        .outerjoin(latest, (Paper.id == latest.c.paper_id) & (latest.c.row_number == 1))
        .where(Paper.id.in_(payload.ids))
    )

    rows = db.execute(stmt).all()
    mapping_by_id = {}
    for row in rows:
        mapping = row._mapping
        paper: Paper = mapping[Paper]
        mapping_by_id[paper.id] = mapping

    headers = [
        "Paper ID",
        "Paper Name",
        "City",
        "State",
        "Website URL",
        "Phone",
        "Mailing Address",
        "County",
        "Chain Owner",
        "CMS Platform",
        "CMS Vendor",
        "Has PDF Edition?",
        "PDF-Only?",
        "Paywall?",
        "Free Public Notices?",
        "Mobile Responsive?",
        "Audit Sources",
        "Audit Notes",
        "Latest Audit Timestamp",
        "Extra Data",
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)

    for paper_id in payload.ids:
        mapping = mapping_by_id.get(paper_id)
        if not mapping:
            continue

        paper: Paper = mapping[Paper]
        timestamp = mapping.get("timestamp")
        extra = json.dumps(paper.extra_data or {}, ensure_ascii=False)

        row = [
            paper.id,
            paper.paper_name or "",
            paper.city or "",
            paper.state or "",
            paper.website_url or "",
            paper.phone or "",
            paper.mailing_address or "",
            paper.county or "",
            mapping.get("chain_owner") or "",
            mapping.get("cms_platform") or "",
            mapping.get("cms_vendor") or "",
            mapping.get("has_pdf") or "",
            mapping.get("pdf_only") or "",
            mapping.get("paywall") or "",
            mapping.get("notices") or "",
            mapping.get("responsive") or "",
            mapping.get("sources") or "",
            mapping.get("notes") or "",
            timestamp.isoformat() if timestamp else "",
            extra,
        ]

        writer.writerow(row)

    csv_data = buffer.getvalue()
    buffer.close()

    response = StreamingResponse(
        iter([csv_data.encode("utf-8")]),
        media_type="text/csv",
    )
    response.headers["Content-Disposition"] = 'attachment; filename="papers_export.csv"'
    return response


def _build_audit_condition(column, normalized: Optional[str]):
    if not normalized:
        return None

    lowered = normalized.lower()

    if lowered == MISSING_OPTION_LABEL.lower():
        return or_(column.is_(None), func.trim(column) == "")

    if lowered == "manual review":
        return func.lower(column).like("manual review%")

    return func.lower(column) == lowered


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
            chain_owner=latest.chain_owner,
            cms_platform=latest.cms_platform,
            cms_vendor=latest.cms_vendor,
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
