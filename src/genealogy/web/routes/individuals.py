from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.db import edits
from genealogy.db.edits import NotFoundError
from genealogy.web.deps import get_conn
from genealogy.web.schemas import IndividualIn, VitalsUpdate
from genealogy.web.serialize import individual_summary as _summary

router = APIRouter(prefix="/api/individuals", tags=["individuals"])


@router.get("")
def list_individuals(
    q: str | None = None,
    surname: str | None = None,
    birth_from: str | None = None,
    birth_to: str | None = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    clauses = []
    params: list = []

    if q:
        clauses.append("(given_names LIKE ? OR surname LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if surname:
        clauses.append("surname LIKE ?")
        params.append(f"%{surname}%")
    if birth_from:
        clauses.append("birth_date_sort >= ?")
        params.append(birth_from)
    if birth_to:
        clauses.append("birth_date_sort <= ?")
        params.append(birth_to)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = conn.execute(f"SELECT COUNT(*) FROM individuals {where}", params).fetchone()[0]

    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    order_by = {
        "name": "surname IS NULL, surname, given_names IS NULL, given_names",
        "birth_asc": "birth_date_sort IS NULL, birth_date_sort",
        "birth_desc": "birth_date_sort IS NULL, birth_date_sort DESC",
    }.get(sort, "surname IS NULL, surname, given_names IS NULL, given_names")

    rows = conn.execute(
        f"SELECT * FROM individuals {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_summary(r) for r in rows],
    }


def _individual_or_404(conn: sqlite3.Connection, individual_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (individual_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="individual not found")
    return row


@router.get("/{individual_id}")
def get_individual(individual_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    row = _individual_or_404(conn, individual_id)
    detail = _summary(row)
    detail["name_prefix"] = row["name_prefix"]
    detail["name_suffix"] = row["name_suffix"]

    detail["events"] = [
        dict(e)
        for e in conn.execute(
            "SELECT * FROM events WHERE owner_type = 'INDI' AND owner_id = ? "
            "ORDER BY date_sort IS NULL, date_sort",
            (individual_id,),
        )
    ]

    families_as_spouse = []
    for fam in conn.execute(
        "SELECT * FROM families WHERE husband_id = ? OR wife_id = ?", (individual_id, individual_id)
    ):
        spouse_id = fam["wife_id"] if fam["husband_id"] == individual_id else fam["husband_id"]
        spouse_row = (
            conn.execute("SELECT * FROM individuals WHERE id = ?", (spouse_id,)).fetchone()
            if spouse_id
            else None
        )
        children = [
            _summary(c)
            for c in conn.execute(
                "SELECT i.* FROM family_children fc JOIN individuals i ON i.id = fc.child_id "
                "WHERE fc.family_id = ? ORDER BY fc.sort_order",
                (fam["id"],),
            )
        ]
        families_as_spouse.append(
            {
                "family_id": fam["id"],
                "spouse": _summary(spouse_row) if spouse_row else None,
                "marriage_date_raw": fam["marriage_date_raw"],
                "marriage_place": fam["marriage_place"],
                "children": children,
            }
        )
    detail["families_as_spouse"] = families_as_spouse

    child_link = conn.execute(
        "SELECT f.* FROM family_children fc JOIN families f ON f.id = fc.family_id "
        "WHERE fc.child_id = ? LIMIT 1",
        (individual_id,),
    ).fetchone()
    if child_link:
        father = (
            conn.execute("SELECT * FROM individuals WHERE id = ?", (child_link["husband_id"],)).fetchone()
            if child_link["husband_id"]
            else None
        )
        mother = (
            conn.execute("SELECT * FROM individuals WHERE id = ?", (child_link["wife_id"],)).fetchone()
            if child_link["wife_id"]
            else None
        )
        detail["family_as_child"] = {
            "family_id": child_link["id"],
            "father": _summary(father) if father else None,
            "mother": _summary(mother) if mother else None,
        }
    else:
        detail["family_as_child"] = None

    citations = []
    for c in conn.execute("SELECT * FROM citations WHERE individual_id = ?", (individual_id,)):
        source = (
            conn.execute("SELECT id, title FROM sources WHERE id = ?", (c["source_id"],)).fetchone()
            if c["source_id"]
            else None
        )
        citations.append(
            {
                "id": c["id"],
                "source": dict(source) if source else None,
                "page": c["page"],
                "quality": c["quality"],
                "note": c["note"],
            }
        )
    detail["citations"] = citations

    return detail


@router.post("", status_code=201)
def create_individual(body: IndividualIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    new_id = edits.create_individual(conn, **body.model_dump())
    return _summary(_individual_or_404(conn, new_id))


@router.put("/{individual_id}")
def update_individual(
    individual_id: int, body: IndividualIn, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _individual_or_404(conn, individual_id)
    edits.update_individual(conn, individual_id, **body.model_dump())
    return _summary(_individual_or_404(conn, individual_id))


def _set_vital(
    conn: sqlite3.Connection, individual_id: int, event_type: str, date_raw: str | None, place: str | None
) -> None:
    event = conn.execute(
        "SELECT id FROM events WHERE owner_type = 'INDI' AND owner_id = ? AND event_type = ?",
        (individual_id, event_type),
    ).fetchone()
    if event:
        edits.update_event(conn, event["id"], date_raw=date_raw, place=place)
    elif date_raw or place:
        edits.add_event(conn, "INDI", individual_id, event_type, date_raw=date_raw, place=place)


@router.put("/{individual_id}/vitals")
def update_vitals(
    individual_id: int, body: VitalsUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _individual_or_404(conn, individual_id)
    _set_vital(conn, individual_id, "BIRT", body.birth_date_raw, body.birth_place)
    _set_vital(conn, individual_id, "DEAT", body.death_date_raw, body.death_place)
    return _summary(_individual_or_404(conn, individual_id))


@router.delete("/{individual_id}", status_code=204)
def delete_individual(individual_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    _individual_or_404(conn, individual_id)
    try:
        edits.delete_individual(conn, individual_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
