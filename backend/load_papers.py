"""CLI utility to load newspaper records into the database."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import delete, select

from .database import SessionLocal
from .models import Audit, Paper
from .import_utils import (
    COLUMN_ALIASES,
    REQUIRED_FIELDS,
    build_lookup_key,
    iter_normalized_rows,
    normalize_columns,
)


def lookup_statement(data: Dict[str, str | None]):
    stmt = select(Paper).where(
        Paper.paper_name == data["paper_name"],
        Paper.city == data["city"],
    )
    state_value = data.get("state")
    if state_value:
        stmt = stmt.where(Paper.state == state_value)
    else:
        stmt = stmt.where(Paper.state.is_(None))
    return stmt


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
                stmt = lookup_statement(data)
                existing = session.execute(stmt).scalars().first() if stmt is not None else None
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
