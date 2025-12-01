"""Create tables for research sessions and related data."""

from __future__ import annotations

from sqlalchemy import text

from ..database import engine


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS research_sessions (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            filter_params JSONB DEFAULT '{}'::jsonb,
            query_string TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS research_session_papers (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
            snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS research_features (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL,
            keywords TEXT[] NOT NULL DEFAULT '{}',
            desired_examples INTEGER NOT NULL DEFAULT 5,
            status VARCHAR NOT NULL DEFAULT 'pending',
            last_evaluated_at TIMESTAMPTZ,
            evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            error TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_research_session_papers_session_id ON research_session_papers(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_research_features_session_id ON research_features(session_id)",
    ]

    with engine.begin() as connection:
        for sql in statements:
            connection.execute(text(sql))


if __name__ == "__main__":
    upgrade()
