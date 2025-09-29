"""Add homepage_html snapshot column to audits."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statement = text(
        """
        ALTER TABLE audits
        ADD COLUMN IF NOT EXISTS homepage_html TEXT
        """
    )

    with engine.begin() as connection:
        connection.execute(statement)


if __name__ == "__main__":
    upgrade()
