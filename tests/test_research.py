import sqlite3

import pytest
from fastapi.testclient import TestClient

from genealogy.db.connection import connect, init_db
from genealogy.db.importer import import_document
from genealogy.gedcom.parser import parse_gedcom
from genealogy.research import uk_sources
from genealogy.research.patriline import get_patriline
from genealogy.web.app import create_app
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    import_document(connection, parse_gedcom(SAMPLE_GEDCOM), source_file="test-fixture")
    yield connection
    connection.close()


def _individual_id(conn, xref):
    return conn.execute("SELECT id FROM individuals WHERE xref_id = ?", (xref,)).fetchone()["id"]


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    init_db(conn)
    import_document(conn, parse_gedcom(SAMPLE_GEDCOM), source_file="test-fixture")
    conn.close()

    app = create_app(db_path)
    return TestClient(app)


def _individual_id_via_api(client, xref):
    results = client.get("/api/individuals", params={"q": ""}).json()["results"]
    for r in results:
        if r["xref_id"] == xref:
            return r["id"]
    raise AssertionError(f"{xref} not found")


# ---------------------------------------------------------------------
# patriline.get_patriline
# ---------------------------------------------------------------------


def test_patriline_walks_father_chain_and_flags_citations(conn):
    alice_id = _individual_id(conn, "@I3@")
    chain = get_patriline(conn, alice_id)

    assert [step["generation"] for step in chain] == [0, 1, 2]
    assert [step["surname"] for step in chain] == ["Smith", "Smith", "Smith"]
    assert [step["given_names"] for step in chain] == ["Alice", "John", "Unknown"]

    alice, john, unknown = chain
    assert alice["has_citation"] is False  # no citation attached to Alice
    assert john["has_citation"] is True  # @S1@ is cited directly on John in the fixture
    assert unknown["has_citation"] is False  # earliest known ancestor -- unsourced, chain ends here


def test_patriline_starting_from_earliest_known_ancestor_is_a_single_step(conn):
    unknown_id = _individual_id(conn, "@I6@")
    chain = get_patriline(conn, unknown_id)
    assert len(chain) == 1
    assert chain[0]["generation"] == 0


def test_patriline_for_person_with_no_recorded_parents(conn):
    francois_id = _individual_id(conn, "@I5@")
    chain = get_patriline(conn, francois_id)
    assert len(chain) == 1
    assert chain[0]["given_names"] == "François"


# ---------------------------------------------------------------------
# uk_sources.build_links
# ---------------------------------------------------------------------


def test_build_links_returns_all_five_sources():
    links = uk_sources.build_links({"given_names": "John", "surname": "Smith", "birth_year": "1850"})
    keys = {link["key"] for link in links}
    assert keys == {"freebmd", "freecen", "freereg", "gro", "discovery"}
    for link in links:
        assert link["url"].startswith("https://")


def test_discovery_link_is_prefilled_with_name_and_years():
    links = uk_sources.build_links(
        {"given_names": "John", "surname": "Smith", "birth_year": "1850", "death_year": "1920"}
    )
    discovery = next(link for link in links if link["key"] == "discovery")
    assert discovery["prefilled"] is True
    assert "discovery.nationalarchives.gov.uk" in discovery["url"]
    assert "_q=John+Smith" in discovery["url"] or "_q=John%20Smith" in discovery["url"]
    assert "_sd=1850" in discovery["url"]
    assert "_ed=1920" in discovery["url"]


def test_form_based_sources_are_not_prefilled():
    links = uk_sources.build_links({"given_names": "John", "surname": "Smith"})
    for key in ("freebmd", "freecen", "freereg", "gro"):
        link = next(link for link in links if link["key"] == key)
        assert link["prefilled"] is False


def test_build_links_handles_missing_facts():
    links = uk_sources.build_links({})
    assert len(links) == 5


# ---------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------


def test_patriline_route(client):
    alice_id = _individual_id_via_api(client, "@I3@")
    resp = client.get(f"/api/individuals/{alice_id}/patriline")
    assert resp.status_code == 200
    chain = resp.json()["chain"]
    assert [step["name"] for step in chain] == ["Alice Smith", "John Smith", "Unknown Smith"]
    assert chain[1]["has_citation"] is True
    assert chain[2]["has_citation"] is False


def test_patriline_route_404(client):
    resp = client.get("/api/individuals/999999/patriline")
    assert resp.status_code == 404


def test_research_links_route_includes_father_surname_in_facts(client):
    alice_id = _individual_id_via_api(client, "@I3@")
    resp = client.get(f"/api/individuals/{alice_id}/research-links")
    assert resp.status_code == 200
    body = resp.json()
    assert body["facts"]["father_surname"] == "Smith"
    assert len(body["links"]) == 5


def test_research_links_route_404(client):
    resp = client.get("/api/individuals/999999/research-links")
    assert resp.status_code == 404
