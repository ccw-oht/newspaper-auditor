"""CLI utility to load newspaper records into the database."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import delete, or_, select

from .database import SessionLocal
from .models import Audit, Paper
from .import_utils import (
    COLUMN_ALIASES,
    REQUIRED_FIELDS,
    build_lookup_key,
    iter_normalized_rows,
    normalize_columns,
    paper_name_match_key,
    website_url_match_key,
)


def find_existing(session, data: Dict[str, str | None]):
    incoming_url_key = website_url_match_key(data.get("website_url"))
    if incoming_url_key:
        stmt = select(Paper).where(Paper.website_url.is_not(None))
        for candidate in session.execute(stmt).scalars().all():
            if website_url_match_key(candidate.website_url) == incoming_url_key:
                return candidate

    incoming_name_key = paper_name_match_key(data.get("paper_name"))
    if not incoming_name_key:
        return None

    stmt = select(Paper)
    city_value = data.get("city")
    if city_value:
        stmt = stmt.where(Paper.city == city_value)
    else:
        stmt = stmt.where(or_(Paper.city.is_(None), Paper.city == ""))

    state_value = data.get("state")
    if state_value:
        stmt = stmt.where(Paper.state == state_value)
    else:
        stmt = stmt.where(or_(Paper.state.is_(None), Paper.state == ""))

    for candidate in session.execute(stmt).scalars().all():
        if paper_name_match_key(candidate.paper_name) == incoming_name_key:
            return candidate

    return None


def apply_update(record: Paper, data: Dict[str, str | None]) -> None:
    for field, value in data.items():
        if field == "extra_data":
            if value:
                record.extra_data = {**(record.extra_data or {}), **value}
        else:
            setattr(record, field, value)


def load_rows(frame: pd.DataFrame, truncate_first: bool = False, dry_run: bool = False) -> Tuple[int, int, int]:
    """Persist rows into the database and return counts (inserted, updated, skipped)."""

    frame = normalize_columns(frame)
    session = SessionLocal()

    inserted = updated = skipped = 0

    try:
        if truncate_first and not dry_run:
            session.execute(delete(Audit))
            session.execute(delete(Paper))
            session.commit()

        cache: Dict[tuple, Paper] = {}

        for idx, (data, _) in enumerate(iter_normalized_rows(frame)):
            missing = [field for field in REQUIRED_FIELDS if not data.get(field)]
            if missing:
                skipped += 1
                continue

            key = build_lookup_key(data)

            existing = cache.get(key)
            if existing is None:
                existing = find_existing(session, data)
                if existing:
                    cache[key] = existing

            if existing:
                apply_update(existing, data)
                cache[key] = existing
                updated += 1
            else:
                new_paper = Paper(**data)
                session.add(new_paper)
                cache[key] = new_paper
                inserted += 1

            if (idx + 1) % 100 == 0 and not dry_run:
                session.flush()

        if not dry_run:
            session.commit()

    finally:
        session.close()

    return inserted, updated, skipped


def run_loader(csv_path: Path, truncate_first: bool = False, dry_run: bool = False) -> Tuple[int, int, int]:
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return load_rows(frame, truncate_first=truncate_first, dry_run=dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load newspaper records into the database")
    parser.add_argument("csv", type=Path, help="Path to the CSV file to ingest")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing records before inserting new ones",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the CSV and report counts without writing to the database",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.csv.exists():
        parser.error(f"CSV file not found: {args.csv}")

    inserted, updated, skipped = run_loader(
        args.csv,
        truncate_first=args.truncate,
        dry_run=args.dry_run,
    )

    mode = "DRY RUN" if args.dry_run else "INGEST"
    print(f"[{mode}] Inserted: {inserted} | Updated: {updated} | Skipped: {skipped}")


if __name__ == "__main__":
    main()
