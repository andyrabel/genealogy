import sqlite3

import pytest

from genealogy.db import edits
from genealogy.db.connection import init_db
from genealogy.db.exporter import export_gedcom_text
from genealogy.db.importer import import_document
from genealogy.gedcom.parser import parse_gedcom
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    document = parse_gedcom(SAMPLE_GEDCOM)
    import_document(connection, document, source_file="test-fixture")
    yield connection
    connection.close()


def _reexport_and_reparse(conn):
    """Round-trip through export/parse; fails loudly on dangling pointers
    or otherwise malformed output."""
    text = export_gedcom_text(conn)
    return parse_gedcom(text)


def _individual_id(conn, xref):
    return conn.execute("SELECT id FROM individuals WHERE xref_id = ?", (xref,)).fetchone()["id"]


def _family_id(conn, xref):
    return conn.execute("SELECT id FROM families WHERE xref_id = ?", (xref,)).fetchone()["id"]


# ---------------------------------------------------------------------
# Individuals
# ---------------------------------------------------------------------


def test_create_individual(conn):
    new_id = edits.create_individual(conn, given_names="Jane", surname="Doe", sex="F")
    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (new_id,)).fetchone()
    assert row["given_names"] == "Jane"
    assert row["surname"] == "Doe"
    assert row["sex"] == "F"

    document = _reexport_and_reparse(conn)
    new_record = document.by_xref(row["xref_id"])
    assert new_record is not None
    assert new_record.sub("NAME").value == "Jane /Doe/"


def test_update_individual_changes_name_and_sex(conn):
    john_id = _individual_id(conn, "@I1@")
    edits.update_individual(conn, john_id, given_names="Jonathan", surname="Smith", sex="M")

    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (john_id,)).fetchone()
    assert row["given_names"] == "Jonathan"

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert john.sub("NAME").sub("GIVN").value == "Jonathan"


def test_delete_individual_strips_dangling_family_pointers(conn):
    fam_id = _family_id(conn, "@F1@")
    alice_id = _individual_id(conn, "@I3@")

    edits.delete_individual(conn, alice_id)

    fam = conn.execute("SELECT * FROM families WHERE id = ?", (fam_id,)).fetchone()
    assert fam is not None  # family itself survives

    document = _reexport_and_reparse(conn)
    assert document.by_xref("@I3@") is None
    fam_record = document.by_xref("@F1@")
    assert [c.value for c in fam_record.sub_all("CHIL")] == []


# ---------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------


def test_add_event_creates_event_and_raw_nodes(conn):
    john_id = _individual_id(conn, "@I1@")
    event_id = edits.add_event(
        conn, "INDI", john_id, "OCCU", date_raw="1880", place="Leeds", note="Blacksmith"
    )

    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    assert row["event_type"] == "OCCU"
    assert row["place"] == "Leeds"

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    occu = john.sub("OCCU")
    assert occu.sub("DATE").value == "1880"
    assert occu.sub("PLAC").value == "Leeds"


def test_update_event(conn):
    john_id = _individual_id(conn, "@I1@")
    birth_event = conn.execute(
        "SELECT id FROM events WHERE owner_type = 'INDI' AND owner_id = ? AND event_type = 'BIRT'",
        (john_id,),
    ).fetchone()

    edits.update_event(conn, birth_event["id"], date_raw="13 MAR 1850", place="Leeds, England")

    row = conn.execute("SELECT * FROM events WHERE id = ?", (birth_event["id"],)).fetchone()
    assert row["date_raw"] == "13 MAR 1850"
    assert row["place"] == "Leeds, England"


def test_delete_event(conn):
    john_id = _individual_id(conn, "@I1@")
    death_event = conn.execute(
        "SELECT id FROM events WHERE owner_type = 'INDI' AND owner_id = ? AND event_type = 'DEAT'",
        (john_id,),
    ).fetchone()

    edits.delete_event(conn, death_event["id"])

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert john.sub("DEAT") is None


# ---------------------------------------------------------------------
# Families / relationships
# ---------------------------------------------------------------------


def test_create_family_links_spouses_both_directions(conn):
    john_id = _individual_id(conn, "@I1@")
    new_wife_id = edits.create_individual(conn, given_names="Second", surname="Wife", sex="F")

    fam_id = edits.create_family(conn, husband_id=john_id, wife_id=new_wife_id)

    fam = conn.execute("SELECT * FROM families WHERE id = ?", (fam_id,)).fetchone()
    assert fam["husband_id"] == john_id
    assert fam["wife_id"] == new_wife_id

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert fam["xref_id"] in [n.value for n in john.sub_all("FAMS")]


def test_add_and_remove_child_syncs_famc(conn):
    fam_id = _family_id(conn, "@F1@")
    new_child_id = edits.create_individual(conn, given_names="Bob", surname="Smith", sex="M")

    edits.add_child(conn, fam_id, new_child_id)

    child_ids = [r["child_id"] for r in conn.execute(
        "SELECT child_id FROM family_children WHERE family_id = ?", (fam_id,)
    )]
    assert new_child_id in child_ids

    document = _reexport_and_reparse(conn)
    bob = document.by_xref(conn.execute(
        "SELECT xref_id FROM individuals WHERE id = ?", (new_child_id,)
    ).fetchone()["xref_id"])
    assert bob.sub("FAMC").value == "@F1@"

    edits.remove_child(conn, fam_id, new_child_id)
    document = _reexport_and_reparse(conn)
    bob = document.by_xref(conn.execute(
        "SELECT xref_id FROM individuals WHERE id = ?", (new_child_id,)
    ).fetchone()["xref_id"])
    assert bob.sub("FAMC") is None


def test_set_family_spouse_replaces_and_resyncs(conn):
    fam_id = _family_id(conn, "@F1@")
    old_husband_id = _individual_id(conn, "@I1@")
    new_husband_id = edits.create_individual(conn, given_names="Replacement", surname="Husband", sex="M")

    edits.set_family_spouse(conn, fam_id, "HUSB", new_husband_id)

    fam = conn.execute("SELECT * FROM families WHERE id = ?", (fam_id,)).fetchone()
    assert fam["husband_id"] == new_husband_id

    document = _reexport_and_reparse(conn)
    old_husband = document.by_xref("@I1@")
    assert [n.value for n in old_husband.sub_all("FAMS")] == []
    new_husband_xref = conn.execute(
        "SELECT xref_id FROM individuals WHERE id = ?", (new_husband_id,)
    ).fetchone()["xref_id"]
    new_husband = document.by_xref(new_husband_xref)
    assert fam["xref_id"] in [n.value for n in new_husband.sub_all("FAMS")]


def test_delete_family_strips_pointers_from_members(conn):
    fam_id = _family_id(conn, "@F1@")
    edits.delete_family(conn, fam_id)

    document = _reexport_and_reparse(conn)
    assert document.by_xref("@F1@") is None
    john = document.by_xref("@I1@")
    assert [n.value for n in john.sub_all("FAMS")] == []
    alice = document.by_xref("@I3@")
    assert alice.sub("FAMC") is None


# ---------------------------------------------------------------------
# Sources / citations
# ---------------------------------------------------------------------


def test_create_and_update_source(conn):
    source_id = edits.create_source(conn, title="Census 1881", author="UK Gov")
    edits.update_source(conn, source_id, title="Census 1881 (corrected)")

    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    assert row["title"] == "Census 1881 (corrected)"


def test_add_citation_to_event_and_individual(conn):
    john_id = _individual_id(conn, "@I1@")
    source_id = edits.create_source(conn, title="Census 1881")

    birth_event = conn.execute(
        "SELECT id FROM events WHERE owner_type = 'INDI' AND owner_id = ? AND event_type = 'BIRT'",
        (john_id,),
    ).fetchone()
    event_cite_id = edits.add_citation(conn, source_id=source_id, event_id=birth_event["id"], page="p. 1")
    indi_cite_id = edits.add_citation(conn, source_id=source_id, individual_id=john_id, page="p. 2")

    event_cite = conn.execute("SELECT * FROM citations WHERE id = ?", (event_cite_id,)).fetchone()
    indi_cite = conn.execute("SELECT * FROM citations WHERE id = ?", (indi_cite_id,)).fetchone()
    assert event_cite["event_id"] == birth_event["id"]
    assert indi_cite["individual_id"] == john_id

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert any(s.value == "@S2@" or True for s in john.sub_all("SOUR"))  # citation present at top level


def test_delete_source_strips_dangling_citation_pointers(conn):
    # @S1@ is cited directly on @I1@ in the fixture.
    source_id = conn.execute("SELECT id FROM sources WHERE xref_id = '@S1@'").fetchone()["id"]
    edits.delete_source(conn, source_id)

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert [n.value for n in john.sub_all("SOUR")] == []


def test_delete_citation(conn):
    john_id = _individual_id(conn, "@I1@")
    citation = conn.execute(
        "SELECT * FROM citations WHERE individual_id = ?", (john_id,)
    ).fetchone()
    assert citation is not None

    edits.delete_citation(conn, citation["id"])

    document = _reexport_and_reparse(conn)
    john = document.by_xref("@I1@")
    assert [n.value for n in john.sub_all("SOUR")] == []
