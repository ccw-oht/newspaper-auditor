"""Add cms_platform column to audits."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statement = "ALTER TABLE audits ADD COLUMN IF NOT EXISTS cms_platform VARCHAR"

    with engine.begin() as connection:
        connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
