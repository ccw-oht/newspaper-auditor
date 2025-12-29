"""Add publication_frequency column to papers."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statement = "ALTER TABLE papers ADD COLUMN IF NOT EXISTS publication_frequency VARCHAR"
    with engine.begin() as connection:
        connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
