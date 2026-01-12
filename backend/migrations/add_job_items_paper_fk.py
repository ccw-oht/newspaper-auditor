"""Add foreign key for job_items.paper_id."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statements = [
        """
        ALTER TABLE job_items
        ADD CONSTRAINT job_items_paper_id_fkey
        FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
        """
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
