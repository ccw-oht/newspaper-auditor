"""Add job queue tables."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS job_queue_state (
            id INTEGER PRIMARY KEY,
            paused BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            job_type VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'pending',
            created_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_count INTEGER DEFAULT 0,
            processed_count INTEGER DEFAULT 0,
            payload JSON,
            result_summary JSON,
            error TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS job_items (
            id INTEGER PRIMARY KEY,
            job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
            paper_id INTEGER,
            status VARCHAR DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error TEXT,
            result JSON
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_job_items_paper_id ON job_items(paper_id)",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
