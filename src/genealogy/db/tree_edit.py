"""Low-level read-write primitives for the raw GEDCOM tree.

These operate directly on `gedcom_records` / `gedcom_nodes` -- the source of
truth for export (see schema.sql). Higher-level domain edits (genealogy.db.edits)
compose these, then call `rebuild_normalized_tables` to refresh the derived
query tables. Nothing here touches the normalized tables directly.
"""

from __future__ import annotations

import re
import sqlite3

_XREF_RE = re.compile(r"^@([A-Za-z]+)(\d+)@$")


def next_xref(conn: sqlite3.Connection, prefix: str) -> str:
    """Return an unused xref like ``@I699@`` for the given prefix (e.g. "I")."""
    rows = conn.execute(
        "SELECT xref_id FROM gedcom_records WHERE xref_id LIKE ?", (f"@{prefix}%@",)
    ).fetchall()
    max_n = 0
    for row in rows:
        match = _XREF_RE.match(row["xref_id"])
        if match and match.group(1) == prefix:
            max_n = max(max_n, int(match.group(2)))
    return f"@{prefix}{max_n + 1}@"


def create_record(conn: sqlite3.Connection, record_type: str, xref_id: str | None = None) -> int:
    if xref_id is None:
        prefix = {"INDI": "I", "FAM": "F", "SOUR": "S"}.get(record_type, "X")
        xref_id = next_xref(conn, prefix)
    max_sort = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM gedcom_records").fetchone()[0]
    cursor = conn.execute(
        "INSERT INTO gedcom_records (record_type, xref_id, value, sort_order) VALUES (?, ?, NULL, ?)",
        (record_type, xref_id, max_sort + 1),
    )
    return cursor.lastrowid


def delete_record(conn: sqlite3.Connection, record_id: int) -> None:
    conn.execute("DELETE FROM gedcom_records WHERE id = ?", (record_id,))


def _next_sort_order(conn: sqlite3.Connection, record_id: int, parent_node_id: int | None) -> int:
    if parent_node_id is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM gedcom_nodes "
            "WHERE record_id = ? AND parent_node_id IS NULL",
            (record_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM gedcom_nodes "
            "WHERE record_id = ? AND parent_node_id = ?",
            (record_id, parent_node_id),
        ).fetchone()
    return row[0] + 1


def add_node(
    conn: sqlite3.Connection,
    record_id: int,
    parent_node_id: int | None,
    level: int,
    tag: str,
    value: str | None,
) -> int:
    sort_order = _next_sort_order(conn, record_id, parent_node_id)
    cursor = conn.execute(
        "INSERT INTO gedcom_nodes (record_id, parent_node_id, level, tag, value, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (record_id, parent_node_id, level, tag, value, sort_order),
    )
    return cursor.lastrowid


def find_child(
    conn: sqlite3.Connection, record_id: int, parent_node_id: int | None, tag: str
) -> sqlite3.Row | None:
    if parent_node_id is None:
        return conn.execute(
            "SELECT * FROM gedcom_nodes WHERE record_id = ? AND parent_node_id IS NULL AND tag = ? "
            "ORDER BY sort_order LIMIT 1",
            (record_id, tag),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM gedcom_nodes WHERE record_id = ? AND parent_node_id = ? AND tag = ? "
        "ORDER BY sort_order LIMIT 1",
        (record_id, parent_node_id, tag),
    ).fetchone()


def delete_node(conn: sqlite3.Connection, node_id: int) -> None:
    conn.execute("DELETE FROM gedcom_nodes WHERE id = ?", (node_id,))


def set_child_value(
    conn: sqlite3.Connection,
    record_id: int,
    parent_node_id: int | None,
    level: int,
    tag: str,
    value: str | None,
) -> int | None:
    """Get-or-create/update/delete-if-cleared for a single-instance child tag.

    Returns the child node's id, or None if the value was cleared and the
    node (which had no children of its own) was removed.
    """
    existing = find_child(conn, record_id, parent_node_id, tag)
    value = value.strip() if isinstance(value, str) else value
    value = value or None

    if existing is None:
        if value is None:
            return None
        return add_node(conn, record_id, parent_node_id, level, tag, value)

    has_children = conn.execute(
        "SELECT 1 FROM gedcom_nodes WHERE parent_node_id = ? LIMIT 1", (existing["id"],)
    ).fetchone()
    if value is None and not has_children:
        delete_node(conn, existing["id"])
        return None

    conn.execute("UPDATE gedcom_nodes SET value = ? WHERE id = ?", (value, existing["id"]))
    return existing["id"]


def remove_pointer_children(conn: sqlite3.Connection, record_id: int, tag: str, target_xref: str) -> None:
    """Delete all children of `record_id` (at any level) with `tag` whose value is `target_xref`.

    Used to strip dangling FAMS/FAMC/HUSB/WIFE/CHIL/SOUR pointers when the
    thing they point at is deleted.
    """
    conn.execute(
        "DELETE FROM gedcom_nodes WHERE record_id = ? AND tag = ? AND value = ?",
        (record_id, tag, target_xref),
    )
