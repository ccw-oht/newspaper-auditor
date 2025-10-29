"""CSV import preview and commit helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..import_utils import BASE_FIELDS, REQUIRED_FIELDS, build_lookup_key, iter_normalized_rows, normalize_columns
from ..models import Paper


@dataclass
class StagedRow:
    temp_id: str
    status: str
    data: Dict[str, str | None]
    existing: Paper | None
    differences: Dict[str, Dict[str, str | None]]
    issues: List[str]


ALLOWED_ACTIONS = {
    "new": ["insert", "skip"],
    "update": ["overwrite", "merge_extra", "skip"],
    "duplicate": ["skip", "overwrite", "merge_extra", "insert"],
    "invalid": ["skip"],
}


def generate_preview(frame: pd.DataFrame, session: Session) -> Tuple[List[StagedRow], Dict[str, int]]:
    normalized = normalize_columns(frame)
    staged: List[StagedRow] = []
    summary = {"new": 0, "update": 0, "duplicate": 0, "invalid": 0}

    cache: Dict[Tuple[str, str, str], Paper | None] = {}
    seen_in_file: Dict[Tuple[str, str, str], str] = {}

    for data, _extras in iter_normalized_rows(normalized):
        temp_id = str(uuid.uuid4())
        issues: List[str] = []
        missing = [field for field in REQUIRED_FIELDS if not data.get(field)]
        if missing:
            issues.append(f"Missing required fields: {', '.join(missing)}")
            staged.append(
                StagedRow(
                    temp_id=temp_id,
                    status="invalid",
                    data=data,
                    existing=None,
                    differences={},
                    issues=issues,
                )
            )
            summary["invalid"] += 1
            continue

        key = build_lookup_key(data)

        existing = cache.get(key)
        if key not in cache:
            existing = _fetch_existing(session, data)
            cache[key] = existing

        status = "new" if existing is None else "update"
        differences: Dict[str, Dict[str, str | None]] = {}

        if existing:
            differences = _compute_differences(existing, data)
            if not differences:
                issues.append("No changes detected; identical to existing record")

        if key in seen_in_file:
            status = "duplicate"
            issues.append("Duplicate row in uploaded file")
            previous_status = _mark_previous_duplicate(staged, seen_in_file[key])
            if previous_status:
                summary[previous_status] -= 1
            summary["duplicate"] += 1
        else:
            seen_in_file[key] = temp_id
            summary[status] += 1

        staged.append(
            StagedRow(
                temp_id=temp_id,
                status=status,
                data=data,
                existing=existing,
                differences=differences,
                issues=issues,
            )
        )

    return staged, summary


def _fetch_existing(session: Session, data: Dict[str, str | None]) -> Paper | None:
    stmt = select(Paper).where(
        Paper.paper_name == data["paper_name"],
        Paper.city == data["city"],
    )
    state_value = data.get("state")
    if state_value:
        stmt = stmt.where(Paper.state == state_value)
    else:
        stmt = stmt.where(Paper.state.is_(None))

    return session.execute(stmt).scalars().first()


def _compute_differences(existing: Paper, data: Dict[str, str | None]) -> Dict[str, Dict[str, str | None]]:
    diffs: Dict[str, Dict[str, str | None]] = {}
    for field in BASE_FIELDS:
        new_val = data.get(field)
        old_val = getattr(existing, field)
        if (new_val or "") != (old_val or ""):
            diffs[field] = {"old": old_val, "new": new_val}

    new_extra = data.get("extra_data") or {}
    old_extra = existing.extra_data or {}

    if new_extra != old_extra:
        diffs["extra_data"] = {"old": old_extra, "new": new_extra}

    return diffs


def _mark_previous_duplicate(staged: List[StagedRow], temp_id: str) -> str | None:
    for staged_row in staged:
        if staged_row.temp_id == temp_id:
            original = staged_row.status
            if staged_row.status != "duplicate":
                staged_row.status = "duplicate"
                staged_row.issues.append("Duplicate row in uploaded file")
            return original
    return None


def allowed_actions(status: str) -> List[str]:
    return ALLOWED_ACTIONS.get(status, ["skip"])


def commit_rows(session: Session, commit_rows: Iterable[schemas.ImportCommitRow]) -> schemas.ImportCommitResult:
    inserted = updated = skipped = 0

    for item in commit_rows:
        action = item.action.lower()
        status = (item.status or "").lower()
        permitted = allowed_actions(status) if status else None
        if permitted is not None and action not in permitted:
            raise ValueError(f"Action '{item.action}' is not permitted for status '{status}'.")

        if action == "skip":
            skipped += 1
            continue

        normalized_data = _sanitize_row_data(item.data)
        extras = normalized_data.pop("extra_data", None)

        if action == "insert":
            paper = Paper(**normalized_data, extra_data=extras or None)
            session.add(paper)
            inserted += 1
            continue

        if action in {"overwrite", "merge_extra"}:
            if item.existing_id is None:
                raise ValueError("existing_id is required for overwrite/merge actions")

            existing = session.get(Paper, item.existing_id)
            if not existing:
                raise ValueError(f"Existing paper {item.existing_id} not found")

            if action == "overwrite":
                for field, value in normalized_data.items():
                    setattr(existing, field, value)
                existing.extra_data = extras or None
            else:  # merge_extra
                for field, value in normalized_data.items():
                    if value:
                        setattr(existing, field, value)
                merged = {**(existing.extra_data or {}), **(extras or {})}
                existing.extra_data = merged or None

            updated += 1
            continue

        raise ValueError(f"Unsupported action: {item.action}")

    session.commit()

    return schemas.ImportCommitResult(inserted=inserted, updated=updated, skipped=skipped)


def _sanitize_row_data(data: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for field in BASE_FIELDS:
        value = data.get(field)
        if isinstance(value, str):
            value = value.strip() or None
        sanitized[field] = value

    extras = data.get("extra_data") or {}
    if not isinstance(extras, dict):
        extras = {}
    sanitized["extra_data"] = extras
    return sanitized
