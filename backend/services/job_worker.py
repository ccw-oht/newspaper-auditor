from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ..database import SessionLocal
from ..models import Job, JobItem, Paper
from . import audit_service, job_queue, lookup_service


POLL_INTERVAL_SECONDS = 2.0
JOB_ITEM_CONCURRENCY = int(os.getenv("JOB_ITEM_CONCURRENCY", "3"))
LOOKUP_JOB_CONCURRENCY = int(os.getenv("LOOKUP_JOB_CONCURRENCY", os.getenv("LOOKUP_BATCH_CONCURRENCY", "1")))


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


def _process_audit(db: Session, item: JobItem) -> tuple[Optional[dict], Optional[str]]:
    paper = db.get(Paper, item.paper_id)
    if not paper:
        return None, "Paper not found"
    audit, results, error_note = audit_service.perform_audit(db, paper)
    payload = {
        "audit_id": audit.id,
        "results": results,
        "error_note": error_note,
    }
    if results is None and error_note:
        return payload, error_note
    return payload, None


def _process_lookup(db: Session, item: JobItem) -> tuple[Optional[dict], Optional[str]]:
    paper = db.get(Paper, item.paper_id)
    if not paper:
        return None, "Paper not found"
    result, logs = lookup_service.lookup_paper_contact_with_logs(db, paper, throttle=False)
    payload = {
        "lookup_metadata": result.lookup_metadata,
        "updated": result.updated,
        "lookup_logs": logs,
    }
    if result.error:
        return payload, result.error
    return payload, None


def _process_job_item(job_id: int, job_type: str, item_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status == "canceled":
            item = db.get(JobItem, item_id)
            if item and item.status in ("pending", "running"):
                item.status = "canceled"
                item.completed_at = datetime.now(timezone.utc)
                item.error = "Canceled"
                db.flush()
                if item.paper_id:
                    paper = db.get(Paper, item.paper_id)
                    if paper:
                        extra = dict(paper.extra_data or {})
                        job_status = dict(extra.get("job_status") or {})
                        job_status[job_type] = {
                            "status": item.status,
                            "error": item.error,
                            "job_id": job_id,
                            "item_id": item.id,
                            "completed_at": item.completed_at.isoformat(),
                        }
                        extra["job_status"] = job_status
                        paper.extra_data = extra
                if job:
                    _summarize_job(db, job)
                db.commit()
            return

        item = db.get(JobItem, item_id)
        if not item or item.status != "pending":
            return
        item.status = "running"
        item.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            if job_type == "audit":
                payload, error = _process_audit(db, item)
            elif job_type == "lookup":
                payload, error = _process_lookup(db, item)
            else:
                payload, error = None, f"Unknown job type: {job_type}"
        except Exception as exc:  # pragma: no cover - defensive for worker runtime
            payload, error = None, str(exc)

        item.result = payload or {}
        item.error = error
        item.completed_at = datetime.now(timezone.utc)
        item.status = "failed" if error else "completed"
        db.flush()

        if item.paper_id:
            paper = db.get(Paper, item.paper_id)
            if paper:
                extra = dict(paper.extra_data or {})
                job_status = dict(extra.get("job_status") or {})
                job_status[job_type] = {
                    "status": item.status,
                    "error": item.error,
                    "job_id": job_id,
                    "item_id": item.id,
                    "completed_at": item.completed_at.isoformat(),
                }
                extra["job_status"] = job_status
                paper.extra_data = extra

        job = db.get(Job, job_id)
        if job:
            _summarize_job(db, job)
        db.commit()


def _process_job(db: Session, job: Job) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    item_ids = [
        item_id
        for (item_id,) in (
            db.query(JobItem.id)
            .filter(JobItem.job_id == job.id, JobItem.status == "pending")
            .order_by(JobItem.id)
            .all()
        )
    ]

    unexpected_errors: list[str] = []
    if item_ids:
        if job.job_type == "lookup":
            max_workers = max(1, min(LOOKUP_JOB_CONCURRENCY, len(item_ids)))
        else:
            max_workers = max(1, min(JOB_ITEM_CONCURRENCY, len(item_ids)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_job_item, job.id, job.job_type, item_id) for item_id in item_ids]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # pragma: no cover - defensive for worker runtime
                    unexpected_errors.append(str(exc))

    db.refresh(job)
    if job.status != "canceled":
        _summarize_job(db, job)
        failed = (job.result_summary or {}).get("failed", 0)
        job.status = "failed" if failed else "completed"
        job.completed_at = datetime.now(timezone.utc)
        if unexpected_errors:
            job.error = "; ".join(unexpected_errors[:3])
        db.commit()
    elif job.completed_at is None:
        job.completed_at = datetime.now(timezone.utc)
        _summarize_job(db, job)
        db.commit()


def run_worker(poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    while True:
        with SessionLocal() as db:
            state = job_queue.get_or_create_state(db)
            if state.paused:
                time.sleep(poll_interval)
                continue

            job = (
                db.query(Job)
                .filter(Job.status == "pending")
                .order_by(Job.created_at)
                .first()
            )
            if not job:
                time.sleep(poll_interval)
                continue

            _process_job(db, job)


if __name__ == "__main__":
    run_worker()
