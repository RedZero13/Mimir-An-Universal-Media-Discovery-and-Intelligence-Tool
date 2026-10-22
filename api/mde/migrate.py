"""Applies migrations/*.sql in filename order, once each. Each file runs in its own transaction."""

from __future__ import annotations

from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migrate(conn: psycopg.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migration ("
        " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migration").fetchall()}
    newly_applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migration (version) VALUES (%s)", (path.stem,))
        newly_applied.append(path.stem)
    return newly_applied
