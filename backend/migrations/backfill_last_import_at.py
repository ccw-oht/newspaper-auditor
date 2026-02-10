"""Backfill import_metadata.last_import_at for papers in an ID range."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Paper


def _has_last_import_at(extra_data: object) -> bool:
    if not isinstance(extra_data, dict):
        return False
    import_meta = extra_data.get("import_metadata")
    if not isinstance(import_meta, dict):
        return False
    value = import_meta.get("last_import_at")
    return isinstance(value, str) and bool(value.strip())


def run_backfill(
    *,
    min_id: int,
    max_id: int | None,
    timestamp: str | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    stamp = (timestamp or datetime.now(timezone.utc).isoformat()).strip()

    with SessionLocal() as session:
        stmt = select(Paper).where(Paper.id >= min_id)
        if max_id is not None:
            stmt = stmt.where(Paper.id <= max_id)
        stmt = stmt.order_by(Paper.id)

        papers = session.execute(stmt).scalars().all()
        scanned = len(papers)
        updated = 0

        for paper in papers:
            if _has_last_import_at(paper.extra_data):
                continue

            extra = dict(paper.extra_data or {})
            import_meta_raw = extra.get("import_metadata")
            import_meta = dict(import_meta_raw) if isinstance(import_meta_raw, dict) else {}
            import_meta["last_import_at"] = stamp
            import_meta["source"] = "csv_import_backfill"
            extra["import_metadata"] = import_meta
            paper.extra_data = extra
            updated += 1

        if not dry_run:
            session.commit()

    return scanned, updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill extra_data.import_metadata.last_import_at for papers."
    )
    parser.add_argument("--min-id", type=int, required=True, help="Minimum Paper ID (inclusive)")
    parser.add_argument("--max-id", type=int, default=None, help="Maximum Paper ID (inclusive)")
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="ISO timestamp to write. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows that would be updated without writing changes.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    scanned, updated = run_backfill(
        min_id=args.min_id,
        max_id=args.max_id,
        timestamp=args.timestamp,
        dry_run=args.dry_run,
    )
    mode = "DRY RUN" if args.dry_run else "BACKFILL"
    print(
        f"[{mode}] Scanned: {scanned} | Updated: {updated} | "
        f"Range: {args.min_id}..{args.max_id if args.max_id is not None else 'max'}"
    )


if __name__ == "__main__":
    main()
