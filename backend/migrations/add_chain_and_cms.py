"""Add chain_owner and cms_vendor columns to audits."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statements = [
        "ALTER TABLE audits ADD COLUMN IF NOT EXISTS chain_owner VARCHAR",
        "ALTER TABLE audits ADD COLUMN IF NOT EXISTS cms_vendor VARCHAR",
    ]

    with engine.begin() as connection:
        for sql in statements:
            connection.execute(text(sql))


if __name__ == "__main__":
    upgrade()
