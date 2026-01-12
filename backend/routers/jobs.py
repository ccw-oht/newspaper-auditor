from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from sqlalchemy.sql import func

from ..models import Job, JobItem, Paper
from ..services import job_queue

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_job(db: Session, job_type: str, ids: List[int]) -> Job:
    job = Job(
        job_type=job_type,
        status="pending",
        created_at=datetime.utcnow(),
        total_count=len(ids),
        processed_count=0,
        payload={"ids": ids},
    )
    db.add(job)
    db.flush()

    items = [JobItem(job_id=job.id, paper_id=int(pid), status="pending") for pid in ids]
    db.add_all(items)
    db.commit()
    db.refresh(job)
    return job


def _summarize_job(db: Session, job: Job) -> None:
    total = job.total_count or 0
    processed = (
        db.query(func.count(JobItem.id))
        .filter(JobItem.job_id == job.id, JobItem.status.in_(["completed", "failed", "canceled"]))
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(JobItem.id))
        .filter(JobItem.job_id == job.id, JobItem.status == "failed")
        .scalar()
        or 0
    )
    succeeded = processed - failed if processed >= failed else 0
    job.processed_count = processed
    job.result_summary = {"total": total, "processed": processed, "succeeded": succeeded, "failed": failed}
    if failed:
        job.error = f"{failed} item{'' if failed == 1 else 's'} failed"
    else:
        job.error = None


@router.post("/audits", response_model=schemas.JobSummaryOut)
def enqueue_audit(payload: schemas.JobCreateRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")
    job = _create_job(db, "audit", payload.ids)
    return job


@router.post("/lookups", response_model=schemas.JobSummaryOut)
def enqueue_lookup(payload: schemas.JobCreateRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")
    job = _create_job(db, "lookup", payload.ids)
    return job


@router.get("/active", response_model=list[schemas.JobSummaryOut])
def list_active_jobs(db: Session = Depends(get_db)):
    return (
        db.query(Job)
        .filter(Job.status.in_(["pending", "running"]))
        .order_by(Job.created_at.desc())
        .all()
    )


@router.get("/active/items", response_model=list[schemas.JobQueueItemOut])
def list_active_items(db: Session = Depends(get_db)):
    rows = (
        db.query(JobItem, Job, Paper)
        .join(Job, Job.id == JobItem.job_id)
        .outerjoin(Paper, Paper.id == JobItem.paper_id)
        .filter(Job.status.in_(["pending", "running"]))
        .order_by(Job.created_at.desc(), JobItem.id.asc())
        .all()
    )
    items: list[schemas.JobQueueItemOut] = []
    for item, job, paper in rows:
        items.append(
            schemas.JobQueueItemOut(
                job_id=job.id,
                job_type=job.job_type,
                item_id=item.id,
                paper_id=item.paper_id,
                paper_name=paper.paper_name if paper else None,
                status=item.status,
            )
        )
    return items


@router.get("/history/items", response_model=list[schemas.JobHistoryItemOut])
def list_history_items(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = (
        db.query(JobItem, Job, Paper)
        .join(Job, Job.id == JobItem.job_id)
        .outerjoin(Paper, Paper.id == JobItem.paper_id)
        .filter(Job.status.in_(["completed", "failed", "canceled"]))
        .order_by(Job.created_at.desc(), JobItem.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items: list[schemas.JobHistoryItemOut] = []
    for item, job, paper in rows:
        items.append(
            schemas.JobHistoryItemOut(
                job_id=job.id,
                job_type=job.job_type,
                job_status=job.status,
                item_id=item.id,
                paper_id=item.paper_id,
                paper_name=paper.paper_name if paper else None,
                status=item.status,
                started_at=item.started_at,
                completed_at=item.completed_at,
                error=item.error,
                result=item.result,
            )
        )
    return items


@router.get("/control", response_model=schemas.JobQueueStateOut)
def get_queue_control(db: Session = Depends(get_db)):
    state = job_queue.get_or_create_state(db)
    return schemas.JobQueueStateOut(paused=state.paused)


@router.post("/control", response_model=schemas.JobQueueStateOut)
def set_queue_control(payload: schemas.JobQueueStateUpdate, db: Session = Depends(get_db)):
    state = job_queue.set_paused(db, payload.paused)
    return schemas.JobQueueStateOut(paused=state.paused)


@router.get("/history", response_model=list[schemas.JobSummaryOut])
def list_history_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return (
        db.query(Job)
        .filter(Job.status.in_(["completed", "failed", "canceled"]))
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{job_id}", response_model=schemas.JobDetailOut)
def get_job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=schemas.JobSummaryOut)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending jobs can be canceled")
    job.status = "canceled"
    job.completed_at = datetime.utcnow()
    db.query(JobItem).filter(JobItem.job_id == job.id, JobItem.status == "pending").update(
        {
            JobItem.status: "canceled",
            JobItem.completed_at: datetime.utcnow(),
            JobItem.error: "Canceled",
        }
    )
    db.commit()
    db.refresh(job)
    return job


@router.delete("/queue")
def clear_queue(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    pending_jobs = db.query(Job).filter(Job.status == "pending").all()
    running_jobs = db.query(Job).filter(Job.status == "running").all()
    job_ids = [job.id for job in pending_jobs]
    running_job_ids = [job.id for job in running_jobs]
    canceled_items = 0

    if job_ids:
        canceled_items += (
            db.query(JobItem)
            .filter(JobItem.job_id.in_(job_ids), JobItem.status == "pending")
            .update(
                {
                    JobItem.status: "canceled",
                    JobItem.completed_at: now,
                    JobItem.error: "Canceled",
                },
                synchronize_session=False,
            )
        )
        for job in pending_jobs:
            job.status = "canceled"
            job.completed_at = now
            _summarize_job(db, job)

    if running_job_ids:
        canceled_items += (
            db.query(JobItem)
            .filter(JobItem.job_id.in_(running_job_ids), JobItem.status.in_(["pending", "running"]))
            .update(
                {
                    JobItem.status: "canceled",
                    JobItem.completed_at: now,
                    JobItem.error: "Canceled",
                },
                synchronize_session=False,
            )
        )
        for job in running_jobs:
            job.status = "canceled"
            job.completed_at = now
            _summarize_job(db, job)

    db.commit()
    return {"canceled_jobs": len(job_ids) + len(running_job_ids), "canceled_items": canceled_items}


@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .filter(Job.status.in_(["completed", "failed", "canceled"]))
        .all()
    )
    if not jobs:
        return {"deleted": 0}
    job_ids = [job.id for job in jobs]
    db.query(JobItem).filter(JobItem.job_id.in_(job_ids)).delete(synchronize_session=False)
    deleted = db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}
