"""SQLite connection helper.

Plain stdlib sqlite3 -- no ORM. The schema is small and fidelity-critical
enough that direct control over the SQL is worth more than ORM convenience.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema_sql = resources.files("genealogy.db").joinpath("schema.sql").read_text()
    conn.executescript(schema_sql)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent column upgrades for databases created before
    schema.sql gained them (CREATE TABLE IF NOT EXISTS doesn't alter
    existing tables)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sources)")}
    if "url" not in columns:
        conn.execute("ALTER TABLE sources ADD COLUMN url TEXT")
