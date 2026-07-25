import pytest
from fastapi.testclient import TestClient

from genealogy.db.connection import connect, init_db
from genealogy.db.importer import import_document
from genealogy.gedcom.parser import parse_gedcom
from genealogy.web.app import create_app
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    init_db(conn)
    import_document(conn, parse_gedcom(SAMPLE_GEDCOM), source_file="test-fixture")
    conn.close()

    app = create_app(db_path)
    return TestClient(app)


def _individual_id(client, xref):
    results = client.get("/api/individuals", params={"q": ""}).json()["results"]
    for r in results:
        if r["xref_id"] == xref:
            return r["id"]
    raise AssertionError(f"{xref} not found")


def test_list_individuals(client):
    resp = client.get("/api/individuals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["results"]) == 5


def test_search_individuals_by_name(client):
    resp = client.get("/api/individuals", params={"q": "Alice"})
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["given_names"] == "Alice"


def test_get_individual_detail(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get(f"/api/individuals/{john_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["surname"] == "Smith"
    assert any(e["event_type"] == "BIRT" for e in body["events"])
    assert len(body["families_as_spouse"]) == 1
    assert body["families_as_spouse"][0]["spouse"]["given_names"] == "Mary"
    assert len(body["citations"]) == 1


def test_get_individual_404(client):
    resp = client.get("/api/individuals/999999")
    assert resp.status_code == 404


def test_create_update_delete_individual(client):
    resp = client.post("/api/individuals", json={"given_names": "New", "surname": "Person", "sex": "F"})
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    resp = client.put(f"/api/individuals/{new_id}", json={"given_names": "Updated", "surname": "Person"})
    assert resp.status_code == 200
    assert resp.json()["given_names"] == "Updated"

    resp = client.delete(f"/api/individuals/{new_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/individuals/{new_id}").status_code == 404


def test_family_detail_and_marriage_update(client):
    john_id = _individual_id(client, "@I1@")
    family_id = client.get(f"/api/individuals/{john_id}").json()["families_as_spouse"][0]["family_id"]

    resp = client.get(f"/api/families/{family_id}")
    assert resp.status_code == 200
    assert resp.json()["marriage_place"] == "Leeds, Yorkshire, England"

    resp = client.put(f"/api/families/{family_id}", json={"date_raw": "4 SEP 1876", "place": "Leeds"})
    assert resp.status_code == 200
    assert resp.json()["marriage_date_raw"] == "4 SEP 1876"


def test_add_and_remove_child(client):
    john_id = _individual_id(client, "@I1@")
    family_id = client.get(f"/api/individuals/{john_id}").json()["families_as_spouse"][0]["family_id"]

    new_child = client.post("/api/individuals", json={"given_names": "Newborn", "surname": "Smith"}).json()

    resp = client.post(f"/api/families/{family_id}/children", json={"child_id": new_child["id"]})
    assert resp.status_code == 201
    assert any(c["id"] == new_child["id"] for c in resp.json()["children"])

    resp = client.delete(f"/api/families/{family_id}/children/{new_child['id']}")
    assert resp.status_code == 200
    assert all(c["id"] != new_child["id"] for c in resp.json()["children"])


def test_create_family(client):
    husband = client.post("/api/individuals", json={"given_names": "H", "surname": "One", "sex": "M"}).json()
    wife = client.post("/api/individuals", json={"given_names": "W", "surname": "One", "sex": "F"}).json()

    resp = client.post("/api/families", json={"husband_id": husband["id"], "wife_id": wife["id"]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["husband"]["id"] == husband["id"]
    assert body["wife"]["id"] == wife["id"]


def test_events_crud(client):
    john_id = _individual_id(client, "@I1@")

    resp = client.post(
        "/api/events",
        json={"owner_type": "INDI", "owner_id": john_id, "event_type": "OCCU", "date_raw": "1880", "place": "Leeds"},
    )
    assert resp.status_code == 201
    event_id = resp.json()["id"]

    resp = client.put(f"/api/events/{event_id}", json={"date_raw": "1881"})
    assert resp.status_code == 200
    assert resp.json()["date_raw"] == "1881"

    resp = client.delete(f"/api/events/{event_id}")
    assert resp.status_code == 204


def test_sources_and_citations_crud(client):
    resp = client.post("/api/sources", json={"title": "Census 1881"})
    assert resp.status_code == 201
    source = resp.json()

    john_id = _individual_id(client, "@I1@")
    resp = client.post(
        "/api/citations", json={"source_id": source["id"], "individual_id": john_id, "page": "p. 9"}
    )
    assert resp.status_code == 201
    citation_id = resp.json()["id"]

    resp = client.get(f"/api/sources/{source['id']}")
    assert resp.status_code == 200
    assert len(resp.json()["citations"]) == 1

    resp = client.delete(f"/api/citations/{citation_id}")
    assert resp.status_code == 204

    resp = client.delete(f"/api/sources/{source['id']}")
    assert resp.status_code == 204


def test_tree_ancestors(client):
    alice_id = _individual_id(client, "@I3@")
    resp = client.get(f"/api/tree/{alice_id}", params={"direction": "ancestors", "generations": 2})
    assert resp.status_code == 200
    body = resp.json()
    names = {n["name"] for n in body["nodes"]}
    assert "John Smith" in names
    assert "Mary Jones" in names


def test_tree_descendants(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get(f"/api/tree/{john_id}", params={"direction": "descendants", "generations": 2})
    assert resp.status_code == 200
    body = resp.json()
    names = {n["name"] for n in body["nodes"]}
    assert "Alice Smith" in names
    assert "Mary Jones" in names


def test_tree_invalid_direction(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get(f"/api/tree/{john_id}", params={"direction": "sideways"})
    assert resp.status_code == 400
