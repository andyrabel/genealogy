"""Import a GEDCOM file into the SQLite raw tree, then rebuild the
normalized tables from it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from genealogy.db.normalize import rebuild_normalized_tables
from genealogy.gedcom.model import GedcomDocument, GedcomNode, GedcomRecord
from genealogy.gedcom.parser import parse_gedcom_bytes


def import_gedcom_file(conn: sqlite3.Connection, path: str | Path) -> GedcomDocument:
    raw = Path(path).read_bytes()
    document = parse_gedcom_bytes(raw)
    import_document(conn, document, source_file=str(path))
    return document


def import_document(
    conn: sqlite3.Connection, document: GedcomDocument, *, source_file: str = "<memory>"
) -> None:
    """Replace the raw tree with `document`'s contents and rebuild normalized tables.

    This is a full replace, not a merge -- re-importing is meant to refresh
    from a fresh export of the same source, not to merge two separate trees.
    """
    conn.execute("DELETE FROM gedcom_nodes")
    conn.execute("DELETE FROM gedcom_records")

    for record in document.records:
        _insert_record(conn, record)

    conn.execute(
        "INSERT INTO import_log (source_file, record_count) VALUES (?, ?)",
        (source_file, len(document.records)),
    )
    conn.commit()

    rebuild_normalized_tables(conn)
    conn.commit()


def _insert_record(conn: sqlite3.Connection, record: GedcomRecord) -> int:
    cursor = conn.execute(
        "INSERT INTO gedcom_records (record_type, xref_id, value, sort_order) "
        "VALUES (?, ?, ?, ?)",
        (record.record_type, record.xref_id, record.value, record.sort_order),
    )
    record_id = cursor.lastrowid
    for seq, child in enumerate(record.children):
        _insert_node(conn, record_id, None, child, seq)
    return record_id


def _insert_node(
    conn: sqlite3.Connection,
    record_id: int,
    parent_node_id: int | None,
    node: GedcomNode,
    seq: int,
) -> int:
    cursor = conn.execute(
        "INSERT INTO gedcom_nodes (record_id, parent_node_id, level, tag, value, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (record_id, parent_node_id, node.level, node.tag, node.value, seq),
    )
    node_id = cursor.lastrowid
    for child_seq, child in enumerate(node.children):
        _insert_node(conn, record_id, node_id, child, child_seq)
    return node_id
