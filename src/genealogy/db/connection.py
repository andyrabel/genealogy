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
    conn.commit()
