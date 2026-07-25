"""Build the normalized query tables (individuals, families, events, ...)
from the raw GEDCOM tree stored in `gedcom_records` / `gedcom_nodes`.

The raw tree is the source of truth for export; these tables exist purely
so the web UI and gap analysis can query efficiently without walking the
tree every time. They are fully rebuilt on every import/edit -- never
hand-edited directly.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from genealogy.gedcom.dates import parse_gedcom_date

INDI_EVENT_TAGS = {
    "BIRT", "CHR", "DEAT", "BURI", "CREM", "ADOP", "BAPM", "BARM", "BASM",
    "BLES", "CHRA", "CONF", "FCOM", "ORDN", "NATU", "EMIG", "IMMI", "CENS",
    "PROB", "WILL", "GRAD", "RETI", "EVEN",
    "CAST", "DSCR", "EDUC", "IDNO", "NATI", "NCHI", "NMR", "OCCU", "PROP",
    "RELI", "RESI", "SSN", "TITL", "FACT",
}

FAM_EVENT_TAGS = {
    "ANUL", "CENS", "DIV", "DIVF", "ENGA", "MARB", "MARC", "MARR", "MARL",
    "MARS", "RESI", "EVEN",
}


@dataclass
class _Tree:
    """In-memory view of one record's gedcom_nodes, grouped by parent."""

    children_by_parent: dict[int | None, list[sqlite3.Row]] = field(default_factory=dict)

    def children(self, parent_id: int | None, tag: str | None = None) -> list[sqlite3.Row]:
        rows = self.children_by_parent.get(parent_id, [])
        return [r for r in rows if tag is None or r["tag"] == tag]

    def first(self, parent_id: int | None, tag: str) -> sqlite3.Row | None:
        for row in self.children(parent_id, tag):
            return row
        return None


def _load_tree(conn: sqlite3.Connection, record_id: int) -> _Tree:
    rows = conn.execute(
        "SELECT id, parent_node_id, level, tag, value FROM gedcom_nodes "
        "WHERE record_id = ? ORDER BY sort_order",
        (record_id,),
    ).fetchall()
    grouped: dict[int | None, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["parent_node_id"]].append(row)
    return _Tree(children_by_parent=grouped)


def rebuild_normalized_tables(conn: sqlite3.Connection) -> None:
    for table in (
        "citations",
        "events",
        "family_children",
        "families",
        "notes",
        "individuals",
        "sources",
    ):
        conn.execute(f"DELETE FROM {table}")

    xref_to_individual_id = _rebuild_individuals(conn)
    _rebuild_sources(conn)
    _rebuild_notes(conn)
    _rebuild_families(conn, xref_to_individual_id)
    _rebuild_individual_events_and_citations(conn)


def _resolve_pointer(value: str | None) -> str | None:
    if value and value.startswith("@") and value.endswith("@"):
        return value
    return None


def _extract_date_place(tree: _Tree, event_node_id: int) -> tuple[str | None, str | None, str | None]:
    date_row = tree.first(event_node_id, "DATE")
    place_row = tree.first(event_node_id, "PLAC")
    date_raw = date_row["value"] if date_row else None
    place = place_row["value"] if place_row else None
    return date_raw, parse_gedcom_date(date_raw), place


def _parse_name(tree: _Tree, name_node: sqlite3.Row | None) -> tuple[str | None, str | None, str | None, str | None]:
    if name_node is None:
        return None, None, None, None

    givn = tree.first(name_node["id"], "GIVN")
    surn = tree.first(name_node["id"], "SURN")
    npfx = tree.first(name_node["id"], "NPFX")
    nsfx = tree.first(name_node["id"], "NSFX")

    if givn or surn:
        return (
            givn["value"] if givn else None,
            surn["value"] if surn else None,
            npfx["value"] if npfx else None,
            nsfx["value"] if nsfx else None,
        )

    # Fall back to parsing "Given Names /Surname/" from the NAME value.
    raw = name_node["value"] or ""
    if "/" in raw:
        given, _, rest = raw.partition("/")
        surname, _, suffix = rest.partition("/")
        return (given.strip() or None, surname.strip() or None, None, suffix.strip() or None)
    return raw.strip() or None, None, None, None


def _rebuild_individuals(conn: sqlite3.Connection) -> dict[str, int]:
    xref_to_id: dict[str, int] = {}
    records = conn.execute(
        "SELECT id, xref_id FROM gedcom_records WHERE record_type = 'INDI'"
    ).fetchall()

    for record in records:
        record_id, xref_id = record["id"], record["xref_id"]
        tree = _load_tree(conn, record_id)

        name_node = tree.first(None, "NAME")
        given, surname, prefix, suffix = _parse_name(tree, name_node)

        sex_row = tree.first(None, "SEX")
        sex = sex_row["value"] if sex_row else None

        birth_row = tree.first(None, "BIRT")
        death_row = tree.first(None, "DEAT")
        birth_raw = birth_sort = birth_place = None
        death_raw = death_sort = death_place = None
        if birth_row:
            birth_raw, birth_sort, birth_place = _extract_date_place(tree, birth_row["id"])
        if death_row:
            death_raw, death_sort, death_place = _extract_date_place(tree, death_row["id"])

        is_living = death_row is None

        cursor = conn.execute(
            """
            INSERT INTO individuals (
                record_id, xref_id, given_names, surname, name_prefix, name_suffix, sex,
                birth_date_raw, birth_date_sort, birth_place,
                death_date_raw, death_date_sort, death_place, is_living
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id, xref_id, given, surname, prefix, suffix, sex,
                birth_raw, birth_sort, birth_place,
                death_raw, death_sort, death_place, int(is_living),
            ),
        )
        xref_to_id[xref_id] = cursor.lastrowid

    return xref_to_id


def _rebuild_sources(conn: sqlite3.Connection) -> None:
    records = conn.execute(
        "SELECT id, xref_id FROM gedcom_records WHERE record_type = 'SOUR'"
    ).fetchall()
    for record in records:
        tree = _load_tree(conn, record["id"])
        titl = tree.first(None, "TITL")
        auth = tree.first(None, "AUTH")
        publ = tree.first(None, "PUBL")
        repo = tree.first(None, "REPO")
        conn.execute(
            """
            INSERT INTO sources (record_id, xref_id, title, author, publication_info, repository_note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"], record["xref_id"],
                titl["value"] if titl else None,
                auth["value"] if auth else None,
                publ["value"] if publ else None,
                repo["value"] if repo else None,
            ),
        )


def _rebuild_notes(conn: sqlite3.Connection) -> None:
    records = conn.execute(
        "SELECT id, value FROM gedcom_records WHERE record_type = 'NOTE'"
    ).fetchall()
    for record in records:
        if record["value"] is not None:
            conn.execute(
                "INSERT INTO notes (record_id, text) VALUES (?, ?)",
                (record["id"], record["value"]),
            )


def _rebuild_families(conn: sqlite3.Connection, xref_to_individual_id: dict[str, int]) -> None:
    records = conn.execute(
        "SELECT id, xref_id FROM gedcom_records WHERE record_type = 'FAM'"
    ).fetchall()

    for record in records:
        record_id, xref_id = record["id"], record["xref_id"]
        tree = _load_tree(conn, record_id)

        husb = tree.first(None, "HUSB")
        wife = tree.first(None, "WIFE")
        husband_id = xref_to_individual_id.get(husb["value"]) if husb else None
        wife_id = xref_to_individual_id.get(wife["value"]) if wife else None

        marr_row = tree.first(None, "MARR")
        marr_raw = marr_sort = marr_place = None
        if marr_row:
            marr_raw, marr_sort, marr_place = _extract_date_place(tree, marr_row["id"])

        cursor = conn.execute(
            """
            INSERT INTO families (
                record_id, xref_id, husband_id, wife_id,
                marriage_date_raw, marriage_date_sort, marriage_place
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, xref_id, husband_id, wife_id, marr_raw, marr_sort, marr_place),
        )
        family_id = cursor.lastrowid

        for seq, chil in enumerate(tree.children(None, "CHIL")):
            child_id = xref_to_individual_id.get(chil["value"])
            if child_id is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO family_children (family_id, child_id, sort_order) "
                    "VALUES (?, ?, ?)",
                    (family_id, child_id, seq),
                )

        for event_tag in FAM_EVENT_TAGS:
            for event_row in tree.children(None, event_tag):
                date_raw, date_sort, place = _extract_date_place(tree, event_row["id"])
                event_cursor = conn.execute(
                    """
                    INSERT INTO events (owner_type, owner_id, node_id, event_type, date_raw, date_sort, place)
                    VALUES ('FAM', ?, ?, ?, ?, ?, ?)
                    """,
                    (family_id, event_row["id"], event_tag, date_raw, date_sort, place),
                )
                _insert_citations_for_node(conn, tree, event_row["id"], event_id=event_cursor.lastrowid)


def _rebuild_individual_events_and_citations(conn: sqlite3.Connection) -> None:
    individuals = conn.execute("SELECT id, record_id, xref_id FROM individuals").fetchall()
    for indi in individuals:
        tree = _load_tree(conn, indi["record_id"])

        for event_tag in INDI_EVENT_TAGS:
            for event_row in tree.children(None, event_tag):
                date_raw, date_sort, place = _extract_date_place(tree, event_row["id"])
                event_cursor = conn.execute(
                    """
                    INSERT INTO events (owner_type, owner_id, node_id, event_type, date_raw, date_sort, place)
                    VALUES ('INDI', ?, ?, ?, ?, ?, ?)
                    """,
                    (indi["id"], event_row["id"], event_tag, date_raw, date_sort, place),
                )
                _insert_citations_for_node(conn, tree, event_row["id"], event_id=event_cursor.lastrowid)

        # Citations attached directly to the individual (not to a specific event).
        for sour_row in tree.children(None, "SOUR"):
            _insert_one_citation(conn, tree, sour_row, event_id=None, individual_id=indi["id"])


def _insert_citations_for_node(conn: sqlite3.Connection, tree: _Tree, node_id: int, *, event_id: int) -> None:
    for sour_row in tree.children(node_id, "SOUR"):
        _insert_one_citation(conn, tree, sour_row, event_id=event_id, individual_id=None)


def _insert_one_citation(
    conn: sqlite3.Connection,
    tree: _Tree,
    sour_row: sqlite3.Row,
    *,
    event_id: int | None,
    individual_id: int | None,
) -> None:
    pointer = _resolve_pointer(sour_row["value"])
    source_id = None
    if pointer:
        row = conn.execute("SELECT id FROM sources WHERE xref_id = ?", (pointer,)).fetchone()
        source_id = row["id"] if row else None

    page_row = tree.first(sour_row["id"], "PAGE")
    quay_row = tree.first(sour_row["id"], "QUAY")
    note_row = tree.first(sour_row["id"], "NOTE")

    conn.execute(
        """
        INSERT INTO citations (source_id, node_id, event_id, individual_id, page, quality, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id, sour_row["id"], event_id, individual_id,
            page_row["value"] if page_row else None,
            quay_row["value"] if quay_row else None,
            note_row["value"] if note_row else None,
        ),
    )
