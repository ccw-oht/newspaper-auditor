from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import JobQueueState


def get_or_create_state(db: Session) -> JobQueueState:
    state = db.query(JobQueueState).first()
    if state is None:
        state = JobQueueState(paused=False, updated_at=datetime.utcnow())
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def set_paused(db: Session, paused: bool) -> JobQueueState:
    state = get_or_create_state(db)
    state.paused = paused
    state.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(state)
    return state
