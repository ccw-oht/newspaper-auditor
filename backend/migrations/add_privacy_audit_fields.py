"""Add privacy audit fields to audits."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statement = text(
        """
        ALTER TABLE audits
            ADD COLUMN IF NOT EXISTS privacy_summary VARCHAR,
            ADD COLUMN IF NOT EXISTS privacy_score INTEGER,
            ADD COLUMN IF NOT EXISTS privacy_flags JSONB DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS privacy_features JSONB DEFAULT '[]'::jsonb
        """
    )

    with engine.begin() as connection:
        connection.execute(statement)


if __name__ == "__main__":
    upgrade()
