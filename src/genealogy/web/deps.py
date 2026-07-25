"""Per-request SQLite connection dependency.

Opens a fresh connection per request rather than sharing one across
requests -- simplest safe option for a local single-user tool, and avoids
sqlite3's same-thread restriction under uvicorn.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from genealogy.db.connection import connect


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()
