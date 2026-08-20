"""Domain-level edits: mutate the raw GEDCOM tree, then rebuild the
normalized tables from it.

Every public function here is a complete, committed unit of work: it
mutates gedcom_records/gedcom_nodes via genealogy.db.tree_edit, calls
rebuild_normalized_tables, and commits. Callers (the web API) never touch
the normalized tables directly.
"""

from __future__ import annotations

import sqlite3

from genealogy.db.normalize import rebuild_normalized_tables
from genealogy.db.tree_edit import (
    add_node,
    create_record,
    delete_record,
    find_child,
    remove_pointer_children,
    set_child_value,
)


class NotFoundError(Exception):
    pass


def _individual_row(conn: sqlite3.Connection, individual_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (individual_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"individual {individual_id} not found")
    return row


def _family_row(conn: sqlite3.Connection, family_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"family {family_id} not found")
    return row


def _finish(conn: sqlite3.Connection) -> None:
    rebuild_normalized_tables(conn)
    conn.commit()


# ---------------------------------------------------------------------
# Individuals
# ---------------------------------------------------------------------


def _write_name(conn: sqlite3.Connection, record_id: int, *, given_names, surname, prefix, suffix) -> None:
    name_node = find_child(conn, record_id, None, "NAME")
    if name_node is None:
        display = f"{given_names or ''} /{surname or ''}/".strip()
        name_node_id = add_node(conn, record_id, None, 1, "NAME", display or None)
    else:
        name_node_id = name_node["id"]
        display = f"{given_names or ''} /{surname or ''}/".strip()
        conn.execute("UPDATE gedcom_nodes SET value = ? WHERE id = ?", (display or None, name_node_id))

    set_child_value(conn, record_id, name_node_id, 2, "GIVN", given_names)
    set_child_value(conn, record_id, name_node_id, 2, "SURN", surname)
    set_child_value(conn, record_id, name_node_id, 2, "NPFX", prefix)
    set_child_value(conn, record_id, name_node_id, 2, "NSFX", suffix)


def create_individual(
    conn: sqlite3.Connection,
    *,
    given_names: str | None = None,
    surname: str | None = None,
    prefix: str | None = None,
    suffix: str | None = None,
    sex: str | None = None,
) -> int:
    record_id = create_record(conn, "INDI")
    _write_name(conn, record_id, given_names=given_names, surname=surname, prefix=prefix, suffix=suffix)
    set_child_value(conn, record_id, None, 1, "SEX", sex)
    _finish(conn)
    row = conn.execute("SELECT id FROM individuals WHERE record_id = ?", (record_id,)).fetchone()
    return row["id"]


def update_individual(
    conn: sqlite3.Connection,
    individual_id: int,
    *,
    given_names: str | None = None,
    surname: str | None = None,
    prefix: str | None = None,
    suffix: str | None = None,
    sex: str | None = None,
) -> None:
    indi = _individual_row(conn, individual_id)
    _write_name(conn, indi["record_id"], given_names=given_names, surname=surname, prefix=prefix, suffix=suffix)
    set_child_value(conn, indi["record_id"], None, 1, "SEX", sex)
    _finish(conn)


def delete_individual(conn: sqlite3.Connection, individual_id: int) -> None:
    indi = _individual_row(conn, individual_id)
    xref = indi["xref_id"]

    fam_records = conn.execute(
        "SELECT gr.id FROM gedcom_records gr WHERE gr.record_type = 'FAM'"
    ).fetchall()
    for fam in fam_records:
        for tag in ("HUSB", "WIFE", "CHIL"):
            remove_pointer_children(conn, fam["id"], tag, xref)

    delete_record(conn, indi["record_id"])
    _finish(conn)


# ---------------------------------------------------------------------
# Events (owner is an individual or a family)
# ---------------------------------------------------------------------


def _owner_record_id(conn: sqlite3.Connection, owner_type: str, owner_id: int) -> int:
    if owner_type == "INDI":
        return _individual_row(conn, owner_id)["record_id"]
    if owner_type == "FAM":
        return _family_row(conn, owner_id)["record_id"]
    raise ValueError(f"invalid owner_type {owner_type!r}")


def add_event(
    conn: sqlite3.Connection,
    owner_type: str,
    owner_id: int,
    event_type: str,
    *,
    date_raw: str | None = None,
    place: str | None = None,
    note: str | None = None,
) -> int:
    record_id = _owner_record_id(conn, owner_type, owner_id)
    event_node_id = add_node(conn, record_id, None, 1, event_type, None)
    set_child_value(conn, record_id, event_node_id, 2, "DATE", date_raw)
    set_child_value(conn, record_id, event_node_id, 2, "PLAC", place)
    set_child_value(conn, record_id, event_node_id, 2, "NOTE", note)
    _finish(conn)
    row = conn.execute("SELECT id FROM events WHERE node_id = ?", (event_node_id,)).fetchone()
    return row["id"]


def _event_row(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"event {event_id} not found")
    return row


def update_event(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    date_raw: str | None = None,
    place: str | None = None,
    note: str | None = None,
) -> None:
    event = _event_row(conn, event_id)
    node = conn.execute("SELECT * FROM gedcom_nodes WHERE id = ?", (event["node_id"],)).fetchone()
    if node is None:
        raise NotFoundError(f"event {event_id} has no underlying node")
    set_child_value(conn, node["record_id"], node["id"], 2, "DATE", date_raw)
    set_child_value(conn, node["record_id"], node["id"], 2, "PLAC", place)
    set_child_value(conn, node["record_id"], node["id"], 2, "NOTE", note)
    _finish(conn)


def delete_event(conn: sqlite3.Connection, event_id: int) -> None:
    event = _event_row(conn, event_id)
    if event["node_id"] is not None:
        conn.execute("DELETE FROM gedcom_nodes WHERE id = ?", (event["node_id"],))
    _finish(conn)


# ---------------------------------------------------------------------
# Families / relationships
# ---------------------------------------------------------------------


def _add_fams(conn: sqlite3.Connection, individual_id: int, family_xref: str) -> None:
    indi = _individual_row(conn, individual_id)
    existing = conn.execute(
        "SELECT id FROM gedcom_nodes WHERE record_id = ? AND parent_node_id IS NULL "
        "AND tag = 'FAMS' AND value = ?",
        (indi["record_id"], family_xref),
    ).fetchone()
    if existing is None:
        add_node(conn, indi["record_id"], None, 1, "FAMS", family_xref)


def create_family(conn: sqlite3.Connection, *, husband_id: int | None = None, wife_id: int | None = None) -> int:
    record_id = create_record(conn, "FAM")
    xref = conn.execute("SELECT xref_id FROM gedcom_records WHERE id = ?", (record_id,)).fetchone()["xref_id"]

    if husband_id is not None:
        husb = _individual_row(conn, husband_id)
        add_node(conn, record_id, None, 1, "HUSB", husb["xref_id"])
        _add_fams(conn, husband_id, xref)
    if wife_id is not None:
        wife = _individual_row(conn, wife_id)
        add_node(conn, record_id, None, 1, "WIFE", wife["xref_id"])
        _add_fams(conn, wife_id, xref)

    _finish(conn)
    row = conn.execute("SELECT id FROM families WHERE record_id = ?", (record_id,)).fetchone()
    return row["id"]


def set_family_spouse(conn: sqlite3.Connection, family_id: int, role: str, individual_id: int | None) -> None:
    if role not in ("HUSB", "WIFE"):
        raise ValueError(f"role must be HUSB or WIFE, got {role!r}")

    fam = _family_row(conn, family_id)
    fam_xref = fam["xref_id"]
    prior_id = fam["husband_id"] if role == "HUSB" else fam["wife_id"]

    if prior_id is not None:
        prior = _individual_row(conn, prior_id)
        remove_pointer_children(conn, prior["record_id"], "FAMS", fam_xref)

    set_child_value(conn, fam["record_id"], None, 1, role, None)

    if individual_id is not None:
        indi = _individual_row(conn, individual_id)
        add_node(conn, fam["record_id"], None, 1, role, indi["xref_id"])
        _add_fams(conn, individual_id, fam_xref)

    _finish(conn)


def add_child(conn: sqlite3.Connection, family_id: int, child_id: int) -> None:
    fam = _family_row(conn, family_id)
    child = _individual_row(conn, child_id)

    existing = conn.execute(
        "SELECT 1 FROM gedcom_nodes WHERE record_id = ? AND parent_node_id IS NULL "
        "AND tag = 'CHIL' AND value = ?",
        (fam["record_id"], child["xref_id"]),
    ).fetchone()
    if existing is None:
        add_node(conn, fam["record_id"], None, 1, "CHIL", child["xref_id"])

    existing_famc = conn.execute(
        "SELECT 1 FROM gedcom_nodes WHERE record_id = ? AND parent_node_id IS NULL "
        "AND tag = 'FAMC' AND value = ?",
        (child["record_id"], fam["xref_id"]),
    ).fetchone()
    if existing_famc is None:
        add_node(conn, child["record_id"], None, 1, "FAMC", fam["xref_id"])

    _finish(conn)


def remove_child(conn: sqlite3.Connection, family_id: int, child_id: int) -> None:
    fam = _family_row(conn, family_id)
    child = _individual_row(conn, child_id)
    remove_pointer_children(conn, fam["record_id"], "CHIL", child["xref_id"])
    remove_pointer_children(conn, child["record_id"], "FAMC", fam["xref_id"])
    _finish(conn)


def delete_family(conn: sqlite3.Connection, family_id: int) -> None:
    fam = _family_row(conn, family_id)
    fam_xref = fam["xref_id"]

    indi_records = conn.execute(
        "SELECT gr.id FROM gedcom_records gr WHERE gr.record_type = 'INDI'"
    ).fetchall()
    for indi in indi_records:
        remove_pointer_children(conn, indi["id"], "FAMS", fam_xref)
        remove_pointer_children(conn, indi["id"], "FAMC", fam_xref)

    delete_record(conn, fam["record_id"])
    _finish(conn)


# ---------------------------------------------------------------------
# Sources / citations
# ---------------------------------------------------------------------


def create_source(
    conn: sqlite3.Connection,
    *,
    title: str | None = None,
    author: str | None = None,
    publication_info: str | None = None,
    repository_note: str | None = None,
    url: str | None = None,
) -> int:
    record_id = create_record(conn, "SOUR")
    set_child_value(conn, record_id, None, 1, "TITL", title)
    set_child_value(conn, record_id, None, 1, "AUTH", author)
    set_child_value(conn, record_id, None, 1, "PUBL", publication_info)
    set_child_value(conn, record_id, None, 1, "REPO", repository_note)
    set_child_value(conn, record_id, None, 1, "_URL", url)
    _finish(conn)
    row = conn.execute("SELECT id FROM sources WHERE record_id = ?", (record_id,)).fetchone()
    return row["id"]


def _source_row(conn: sqlite3.Connection, source_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"source {source_id} not found")
    return row


def update_source(
    conn: sqlite3.Connection,
    source_id: int,
    *,
    title: str | None = None,
    author: str | None = None,
    publication_info: str | None = None,
    repository_note: str | None = None,
    url: str | None = None,
) -> None:
    source = _source_row(conn, source_id)
    set_child_value(conn, source["record_id"], None, 1, "TITL", title)
    set_child_value(conn, source["record_id"], None, 1, "AUTH", author)
    set_child_value(conn, source["record_id"], None, 1, "PUBL", publication_info)
    set_child_value(conn, source["record_id"], None, 1, "REPO", repository_note)
    set_child_value(conn, source["record_id"], None, 1, "_URL", url)
    _finish(conn)


def delete_source(conn: sqlite3.Connection, source_id: int) -> None:
    source = _source_row(conn, source_id)
    xref = source["xref_id"]

    records = conn.execute("SELECT id FROM gedcom_records").fetchall()
    for record in records:
        remove_pointer_children(conn, record["id"], "SOUR", xref)

    delete_record(conn, source["record_id"])
    _finish(conn)


def _citation_row(conn: sqlite3.Connection, citation_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM citations WHERE id = ?", (citation_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"citation {citation_id} not found")
    return row


def add_citation(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    event_id: int | None = None,
    individual_id: int | None = None,
    page: str | None = None,
    quality: str | None = None,
    note: str | None = None,
) -> int:
    if (event_id is None) == (individual_id is None):
        raise ValueError("exactly one of event_id or individual_id must be given")

    source = _source_row(conn, source_id)

    if event_id is not None:
        event = _event_row(conn, event_id)
        if event["node_id"] is None:
            raise NotFoundError(f"event {event_id} has no underlying node")
        event_node = conn.execute("SELECT * FROM gedcom_nodes WHERE id = ?", (event["node_id"],)).fetchone()
        record_id = event_node["record_id"]
        parent_node_id = event_node["id"]
        level = 2
    else:
        indi = _individual_row(conn, individual_id)
        record_id = indi["record_id"]
        parent_node_id = None
        level = 1

    sour_node_id = add_node(conn, record_id, parent_node_id, level, "SOUR", source["xref_id"])
    set_child_value(conn, record_id, sour_node_id, level + 1, "PAGE", page)
    set_child_value(conn, record_id, sour_node_id, level + 1, "QUAY", quality)
    set_child_value(conn, record_id, sour_node_id, level + 1, "NOTE", note)

    _finish(conn)
    row = conn.execute("SELECT id FROM citations WHERE node_id = ?", (sour_node_id,)).fetchone()
    return row["id"]


def delete_citation(conn: sqlite3.Connection, citation_id: int) -> None:
    citation = _citation_row(conn, citation_id)
    if citation["node_id"] is not None:
        conn.execute("DELETE FROM gedcom_nodes WHERE id = ?", (citation["node_id"],))
    _finish(conn)
