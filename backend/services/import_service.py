"""CSV import preview and commit helpers."""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from sqlalchemy import func, select
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
    "possible_duplicate": ["skip", "overwrite", "merge_extra", "insert"],
    "invalid": ["skip"],
}

PROTECTED_METADATA_FIELDS = ("cms_platform", "cms_vendor")


def generate_preview(frame: pd.DataFrame, session: Session) -> Tuple[List[StagedRow], Dict[str, int]]:
    normalized = normalize_columns(frame)
    staged: List[StagedRow] = []
    summary = {"new": 0, "update": 0, "duplicate": 0, "possible_duplicate": 0, "invalid": 0}

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

        if existing is None:
            fuzzy_match = _find_fuzzy_match(session, data)
            if fuzzy_match is not None:
                existing = fuzzy_match
                status = "possible_duplicate"
                issues.append(f"Possible duplicate of '{existing.paper_name}' (id {existing.id}).")
                differences = _compute_differences(existing, data)
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
    city_value = (data.get("city") or "").strip().lower()
    name_value = (data.get("paper_name") or "").strip().lower()
    stmt = select(Paper).where(
        func.lower(func.trim(Paper.paper_name)) == name_value,
        func.lower(func.trim(Paper.city)) == city_value,
    )
    state_value = data.get("state")
    if state_value:
        stmt = stmt.where(func.lower(func.trim(Paper.state)) == state_value.strip().lower())
    else:
        stmt = stmt.where(
            (Paper.state.is_(None)) | (func.trim(Paper.state) == "")
        )

    return session.execute(stmt).scalars().first()


def _normalize_name(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^\w\s,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for suffix in (", the", ", a", ", an"):
        if cleaned.endswith(suffix):
            base = cleaned[: -len(suffix)].strip()
            article = suffix.replace(",", "").strip()
            cleaned = f"{article} {base}".strip()
            break
    return cleaned


def _name_variants(value: str) -> set[str]:
    variants = {_normalize_name(value)}
    for article in ("the ", "a ", "an "):
        if any(name.startswith(article) for name in variants):
            for name in list(variants):
                if name.startswith(article):
                    variants.add(name[len(article):])
    return {name for name in variants if name}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _find_fuzzy_match(session: Session, data: Dict[str, str | None]) -> Paper | None:
    name = data.get("paper_name") or ""
    city = data.get("city") or ""
    if not name.strip() or not city.strip():
        return None

    stmt = select(Paper).where(func.lower(func.trim(Paper.city)) == city.strip().lower())
    state_value = data.get("state")
    if state_value:
        stmt = stmt.where(func.lower(func.trim(Paper.state)) == state_value.strip().lower())
    else:
        stmt = stmt.where(
            (Paper.state.is_(None)) | (func.trim(Paper.state) == "")
        )

    candidates = session.execute(stmt).scalars().all()
    if not candidates:
        return None

    incoming_variants = _name_variants(name)
    best_match = None
    best_score = 0.0
    for candidate in candidates:
        candidate_name = candidate.paper_name or ""
        if not candidate_name.strip():
            continue
        candidate_variants = _name_variants(candidate_name)
        score = max(
            _similarity(a, b) for a in incoming_variants for b in candidate_variants
        )
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match and best_score >= 0.9:
        return best_match
    return None


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


def _collect_protected_overrides(data: Dict[str, Any]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    for field in PROTECTED_METADATA_FIELDS:
        raw_value = data.get(field)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            cleaned = raw_value.strip()
        else:
            cleaned = str(raw_value).strip()
        if not cleaned:
            continue
        if cleaned.lower().startswith("manual review"):
            continue
        overrides[field] = cleaned
    return overrides


def _apply_override_updates(paper: Paper, overrides: Dict[str, str]) -> None:
    if not overrides:
        return

    merged = dict(paper.audit_overrides or {})
    changed = False
    for field, value in overrides.items():
        if merged.get(field) == value:
            continue
        merged[field] = value
        changed = True

    if changed:
        paper.audit_overrides = merged or None


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
        override_values = _collect_protected_overrides(normalized_data)
        field_actions = item.field_actions or {}

        if action == "insert":
            paper = Paper(
                **normalized_data,
                extra_data=extras or None,
                audit_overrides=override_values or None,
            )
            session.add(paper)
            inserted += 1
            continue

        if action in {"overwrite", "merge_extra"}:
            if item.existing_id is None:
                raise ValueError("existing_id is required for overwrite/merge actions")

            existing = session.get(Paper, item.existing_id)
            if not existing:
                raise ValueError(f"Existing paper {item.existing_id} not found")

            if field_actions:
                for field, value in normalized_data.items():
                    if field_actions.get(field) == "overwrite":
                        setattr(existing, field, value)
            else:
                if action == "overwrite":
                    for field, value in normalized_data.items():
                        setattr(existing, field, value)
                else:  # merge_extra
                    for field, value in normalized_data.items():
                        if value:
                            setattr(existing, field, value)

            if action == "overwrite":
                existing.extra_data = extras or None
            else:
                merged = {**(existing.extra_data or {}), **(extras or {})}
                existing.extra_data = merged or None

            _apply_override_updates(existing, override_values)
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
