"""Export the database back to GEDCOM text.

Reconstructs a GedcomDocument purely from the raw tree tables
(gedcom_records / gedcom_nodes), which are the source of truth -- this is
what gives round-trip fidelity, independent of what the normalized tables
do or don't model.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from genealogy.gedcom.model import GedcomDocument, GedcomNode, GedcomRecord
from genealogy.gedcom.writer import write_gedcom


def export_document(conn: sqlite3.Connection) -> GedcomDocument:
    document = GedcomDocument()

    records = conn.execute(
        "SELECT id, record_type, xref_id, value, sort_order FROM gedcom_records "
        "ORDER BY sort_order"
    ).fetchall()

    all_nodes = conn.execute(
        "SELECT id, record_id, parent_node_id, level, tag, value FROM gedcom_nodes "
        "ORDER BY record_id, sort_order"
    ).fetchall()

    nodes_by_record: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in all_nodes:
        nodes_by_record[row["record_id"]].append(row)

    for record_row in records:
        record = GedcomRecord(
            record_type=record_row["record_type"],
            xref_id=record_row["xref_id"],
            value=record_row["value"],
            sort_order=record_row["sort_order"],
        )
        record.children = _build_node_tree(nodes_by_record.get(record_row["id"], []))
        document.records.append(record)

    _force_utf8_header(document)
    return document


def _force_utf8_header(document: GedcomDocument) -> None:
    """Ensure HEAD.CHAR says UTF-8, since export always writes UTF-8 bytes.

    Without this, a file whose original HEAD.CHAR said e.g. ANSI would be
    re-imported using the wrong codec and corrupt any non-ASCII text (an
    everyday occurrence in genealogy: accented names, place names, etc.).
    """
    for record in document.records:
        if record.record_type == "HEAD":
            char_node = record.sub("CHAR")
            if char_node is not None:
                char_node.value = "UTF-8"
            else:
                record.children.append(GedcomNode(level=1, tag="CHAR", value="UTF-8"))
            return


def _build_node_tree(rows: list[sqlite3.Row]) -> list[GedcomNode]:
    nodes_by_id: dict[int, GedcomNode] = {}
    children_of: dict[int | None, list[int]] = defaultdict(list)

    for row in rows:
        nodes_by_id[row["id"]] = GedcomNode(level=row["level"], tag=row["tag"], value=row["value"])
        children_of[row["parent_node_id"]].append(row["id"])

    def attach(parent_id: int | None) -> list[GedcomNode]:
        result = []
        for node_id in children_of.get(parent_id, []):
            node = nodes_by_id[node_id]
            node.children = attach(node_id)
            result.append(node)
        return result

    return attach(None)


def export_gedcom_text(conn: sqlite3.Connection) -> str:
    return write_gedcom(export_document(conn))


def export_gedcom_file(conn: sqlite3.Connection, path: str | Path) -> None:
    text = export_gedcom_text(conn)
    Path(path).write_bytes(text.encode("utf-8-sig"))
