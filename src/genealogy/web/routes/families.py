from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.db import edits
from genealogy.web.deps import get_conn
from genealogy.web.schemas import ChildIn, FamilyCreate, MarriageUpdate, SpouseUpdate
from genealogy.web.serialize import individual_summary as _summary

router = APIRouter(prefix="/api/families", tags=["families"])


def _family_or_404(conn: sqlite3.Connection, family_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="family not found")
    return row


def _detail(conn: sqlite3.Connection, fam: sqlite3.Row) -> dict:
    husband = (
        conn.execute("SELECT * FROM individuals WHERE id = ?", (fam["husband_id"],)).fetchone()
        if fam["husband_id"]
        else None
    )
    wife = (
        conn.execute("SELECT * FROM individuals WHERE id = ?", (fam["wife_id"],)).fetchone()
        if fam["wife_id"]
        else None
    )
    children = []
    for c in conn.execute(
        "SELECT i.* FROM family_children fc JOIN individuals i ON i.id = fc.child_id "
        "WHERE fc.family_id = ? ORDER BY fc.sort_order",
        (fam["id"],),
    ):
        child = _summary(c)
        own_family = conn.execute(
            "SELECT id FROM families WHERE husband_id = ? OR wife_id = ? LIMIT 1", (c["id"], c["id"])
        ).fetchone()
        child["own_family_id"] = own_family["id"] if own_family else None
        children.append(child)
    return {
        "id": fam["id"],
        "xref_id": fam["xref_id"],
        "husband": _summary(husband) if husband else None,
        "wife": _summary(wife) if wife else None,
        "marriage_date_raw": fam["marriage_date_raw"],
        "marriage_place": fam["marriage_place"],
        "children": children,
    }


@router.get("")
def list_families(
    surname: str | None = None,
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    clauses = []
    params: list = []
    if surname:
        clauses.append(
            "(husband_id IN (SELECT id FROM individuals WHERE surname LIKE ?) "
            "OR wife_id IN (SELECT id FROM individuals WHERE surname LIKE ?))"
        )
        params.extend([f"%{surname}%", f"%{surname}%"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = conn.execute(f"SELECT COUNT(*) FROM families {where}", params).fetchone()[0]

    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM families {where} ORDER BY id LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_detail(conn, r) for r in rows],
    }


@router.post("", status_code=201)
def create_family(body: FamilyCreate, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    family_id = edits.create_family(conn, husband_id=body.husband_id, wife_id=body.wife_id)
    return _detail(conn, _family_or_404(conn, family_id))


@router.get("/{family_id}")
def get_family(family_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _detail(conn, _family_or_404(conn, family_id))


@router.put("/{family_id}/spouse")
def update_spouse(
    family_id: int, body: SpouseUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _family_or_404(conn, family_id)
    if body.role not in ("HUSB", "WIFE"):
        raise HTTPException(status_code=400, detail="role must be HUSB or WIFE")
    edits.set_family_spouse(conn, family_id, body.role, body.individual_id)
    return _detail(conn, _family_or_404(conn, family_id))


@router.put("/{family_id}")
def update_marriage(
    family_id: int, body: MarriageUpdate, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _family_or_404(conn, family_id)
    marr_event = conn.execute(
        "SELECT id FROM events WHERE owner_type = 'FAM' AND owner_id = ? AND event_type = 'MARR'",
        (family_id,),
    ).fetchone()
    if marr_event:
        edits.update_event(conn, marr_event["id"], date_raw=body.date_raw, place=body.place)
    else:
        edits.add_event(conn, "FAM", family_id, "MARR", date_raw=body.date_raw, place=body.place)
    return _detail(conn, _family_or_404(conn, family_id))


@router.post("/{family_id}/children", status_code=201)
def add_child(family_id: int, body: ChildIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _family_or_404(conn, family_id)
    edits.add_child(conn, family_id, body.child_id)
    return _detail(conn, _family_or_404(conn, family_id))


@router.delete("/{family_id}/children/{child_id}")
def remove_child(
    family_id: int, child_id: int, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _family_or_404(conn, family_id)
    edits.remove_child(conn, family_id, child_id)
    return _detail(conn, _family_or_404(conn, family_id))


@router.delete("/{family_id}", status_code=204)
def delete_family(family_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    _family_or_404(conn, family_id)
    edits.delete_family(conn, family_id)
