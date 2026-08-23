import sqlite3

import pytest

from genealogy.db.connection import init_db
from genealogy.db.exporter import export_document, export_gedcom_text
from genealogy.db.importer import import_document
from genealogy.gedcom.parser import parse_gedcom
from genealogy.gedcom.writer import write_gedcom
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM
from tests.gedcom_helpers import doc_to_tuple


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def imported_conn(conn):
    document = parse_gedcom(SAMPLE_GEDCOM)
    import_document(conn, document, source_file="test-fixture")
    return conn


def test_individuals_normalized(imported_conn):
    rows = {r["xref_id"]: r for r in imported_conn.execute("SELECT * FROM individuals")}
    assert len(rows) == 6

    john = rows["@I1@"]
    assert john["given_names"] == "John"
    assert john["surname"] == "Smith"
    assert john["sex"] == "M"
    assert john["birth_date_sort"] == "1850-03-12"
    assert john["death_date_sort"] == "1920-00-00"
    assert john["is_living"] == 0

    # Born 1855, no DEAT recorded -- old enough to be presumed deceased
    # rather than shown as living.
    mary = rows["@I2@"]
    assert mary["is_living"] == 0
    assert mary["birth_date_sort"] == "1855-00-00"

    # No birth date and no DEAT -- can't apply the age heuristic, so still
    # presumed living.
    unknown_ancestor = rows["@I4@"]
    assert unknown_ancestor["birth_date_sort"] is None
    assert unknown_ancestor["is_living"] == 1


def test_families_and_children(imported_conn):
    fam = imported_conn.execute("SELECT * FROM families").fetchone()
    assert fam["marriage_date_sort"] == "1876-09-03"

    john_id = imported_conn.execute(
        "SELECT id FROM individuals WHERE xref_id = '@I1@'"
    ).fetchone()["id"]
    mary_id = imported_conn.execute(
        "SELECT id FROM individuals WHERE xref_id = '@I2@'"
    ).fetchone()["id"]
    assert fam["husband_id"] == john_id
    assert fam["wife_id"] == mary_id

    alice_id = imported_conn.execute(
        "SELECT id FROM individuals WHERE xref_id = '@I3@'"
    ).fetchone()["id"]
    child_ids = [
        r["child_id"]
        for r in imported_conn.execute(
            "SELECT child_id FROM family_children WHERE family_id = ?", (fam["id"],)
        )
    ]
    assert child_ids == [alice_id]


def test_events_include_birth_death_and_marriage(imported_conn):
    event_types = {r["event_type"] for r in imported_conn.execute("SELECT event_type FROM events")}
    assert {"BIRT", "DEAT", "MARR"} <= event_types


def test_sources_and_citations(imported_conn):
    source = imported_conn.execute("SELECT * FROM sources").fetchone()
    assert source["title"] == "Parish Registers of Leeds, Yorkshire"
    assert source["url"] == "https://example.org/archives/leeds-parish-registers"

    citation = imported_conn.execute("SELECT * FROM citations").fetchone()
    assert citation["source_id"] == source["id"]
    assert citation["page"] == "p. 42"
    assert citation["quality"] == "2"

    john_id = imported_conn.execute(
        "SELECT id FROM individuals WHERE xref_id = '@I1@'"
    ).fetchone()["id"]
    assert citation["individual_id"] == john_id


def test_shared_note_record(imported_conn):
    note = imported_conn.execute("SELECT * FROM notes").fetchone()
    assert note["text"] == "This is a shared note record.\nIt has a second line via CONT."


def test_export_round_trips_through_database(imported_conn):
    original = parse_gedcom(SAMPLE_GEDCOM)
    exported_text = export_gedcom_text(imported_conn)
    reexported_document = parse_gedcom(exported_text)

    # The fixture already declares CHAR UTF-8, so the exporter's forced
    # UTF-8 header rewrite is a no-op here and the tree should match exactly.
    assert doc_to_tuple(reexported_document) == doc_to_tuple(original)


def test_export_forces_utf8_header_when_declared_otherwise(conn):
    ansi_gedcom = SAMPLE_GEDCOM.replace("1 CHAR UTF-8", "1 CHAR ANSI")
    document = parse_gedcom(ansi_gedcom)
    import_document(conn, document, source_file="test-fixture-ansi")

    exported_document = export_document(conn)
    head = exported_document.by_type("HEAD")[0]
    assert head.sub("CHAR").value == "UTF-8"
