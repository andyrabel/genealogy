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


def test_update_vitals_creates_and_updates_events(client):
    john_id = _individual_id(client, "@I1@")
    original = client.get(f"/api/individuals/{john_id}").json()
    assert original["birth_date_raw"]

    resp = client.put(
        f"/api/individuals/{john_id}/vitals",
        json={
            "birth_date_raw": "1 JAN 1840",
            "birth_place": "York, England",
            "death_date_raw": "1900",
            "death_place": "Leeds, England",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["birth_date_raw"] == "1 JAN 1840"
    assert body["birth_place"] == "York, England"
    assert body["death_date_raw"] == "1900"
    assert body["death_place"] == "Leeds, England"

    detail = client.get(f"/api/individuals/{john_id}").json()
    birth_events = [e for e in detail["events"] if e["event_type"] == "BIRT"]
    assert len(birth_events) == 1
    assert birth_events[0]["date_raw"] == "1 JAN 1840"

    new_person = client.post("/api/individuals", json={"given_names": "New", "surname": "Person"}).json()
    resp = client.put(
        f"/api/individuals/{new_person['id']}/vitals",
        json={"birth_date_raw": "1950", "birth_place": None, "death_date_raw": None, "death_place": None},
    )
    assert resp.status_code == 200
    assert resp.json()["birth_date_raw"] == "1950"
    assert resp.json()["death_date_raw"] is None


def test_list_families(client):
    resp = client.get("/api/families")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(f["husband"] and f["husband"]["surname"] == "Smith" for f in body["results"])

    resp = client.get("/api/families", params={"surname": "Smith"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(
        (f["husband"] and f["husband"]["surname"] == "Smith") or (f["wife"] and f["wife"]["surname"] == "Smith")
        for f in body["results"]
    )

    resp = client.get("/api/families", params={"surname": "NoSuchSurname"})
    assert resp.json()["total"] == 0


def test_family_detail_and_marriage_update(client):
    john_id = _individual_id(client, "@I1@")
    family_id = client.get(f"/api/individuals/{john_id}").json()["families_as_spouse"][0]["family_id"]

    resp = client.get(f"/api/families/{family_id}")
    assert resp.status_code == 200
    assert resp.json()["marriage_place"] == "Leeds, Yorkshire, England"

    resp = client.put(f"/api/families/{family_id}", json={"date_raw": "4 SEP 1876", "place": "Leeds"})
    assert resp.status_code == 200
    assert resp.json()["marriage_date_raw"] == "4 SEP 1876"


def test_family_children_include_own_family_id(client):
    alice_id = _individual_id(client, "@I3@")
    john_id = _individual_id(client, "@I1@")
    family_id = client.get(f"/api/individuals/{john_id}").json()["families_as_spouse"][0]["family_id"]

    detail = client.get(f"/api/families/{family_id}").json()
    alice = next(c for c in detail["children"] if c["id"] == alice_id)
    assert alice["own_family_id"] is None

    spouse = client.post("/api/individuals", json={"given_names": "Bob", "surname": "Someone"}).json()
    alice_family = client.post("/api/families", json={"husband_id": spouse["id"], "wife_id": alice_id}).json()

    detail = client.get(f"/api/families/{family_id}").json()
    alice = next(c for c in detail["children"] if c["id"] == alice_id)
    assert alice["own_family_id"] == alice_family["id"]


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


def test_descendants_outline(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get(f"/api/reports/descendants/{john_id}")
    assert resp.status_code == 200
    root = resp.json()["root"]

    assert root["name"] == "John Smith"
    assert root["generation"] == 1
    assert len(root["unions"]) == 1

    union = root["unions"][0]
    assert union["spouse"]["name"] == "Mary Jones"
    assert union["marriage_date_raw"] == "3 SEP 1876"
    assert union["ordinal"] == 1
    assert union["total_unions"] == 1

    children = union["children"]
    assert len(children) == 1
    assert children[0]["name"] == "Alice Smith"
    assert children[0]["generation"] == 2
    assert children[0]["unions"] == []


def test_descendants_outline_404(client):
    resp = client.get("/api/reports/descendants/999999")
    assert resp.status_code == 404


def test_direct_line(client):
    john_id = _individual_id(client, "@I1@")
    alice_id = _individual_id(client, "@I3@")
    resp = client.get("/api/reports/direct-line", params={"from_id": john_id, "to_id": alice_id})
    assert resp.status_code == 200
    steps = resp.json()["steps"]

    assert len(steps) == 2
    assert steps[0]["name"] == "John Smith"
    assert steps[0]["generation"] == 1
    assert steps[0]["spouse"]["name"] == "Mary Jones"
    assert steps[0]["marriage_date_raw"] == "3 SEP 1876"

    assert steps[1]["name"] == "Alice Smith"
    assert steps[1]["generation"] == 2
    assert steps[1]["spouse"] is None


def test_direct_line_same_person(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get("/api/reports/direct-line", params={"from_id": john_id, "to_id": john_id})
    assert resp.status_code == 200
    steps = resp.json()["steps"]
    assert len(steps) == 1
    assert steps[0]["name"] == "John Smith"


def test_direct_line_unrelated_404(client):
    john_id = _individual_id(client, "@I1@")
    francois_id = _individual_id(client, "@I5@")
    resp = client.get("/api/reports/direct-line", params={"from_id": john_id, "to_id": francois_id})
    assert resp.status_code == 404


def test_direct_line_missing_person_404(client):
    john_id = _individual_id(client, "@I1@")
    resp = client.get("/api/reports/direct-line", params={"from_id": john_id, "to_id": 999999})
    assert resp.status_code == 404
