"""Read-only research views: UK record-search links and the direct
male-line (patriline) chain for a person. Thin route layer -- the actual
logic lives in `genealogy.research`, same split as `reports.py`."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.research import uk_sources
from genealogy.research.patriline import get_patriline
from genealogy.web.deps import get_conn
from genealogy.web.serialize import year_of

router = APIRouter(prefix="/api/individuals", tags=["research"])


def _individual_or_404(conn: sqlite3.Connection, individual_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (individual_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="individual not found")
    return row


def _facts(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    father_surname = None
    child_link = conn.execute(
        "SELECT f.* FROM family_children fc JOIN families f ON f.id = fc.family_id "
        "WHERE fc.child_id = ? LIMIT 1",
        (row["id"],),
    ).fetchone()
    if child_link and child_link["husband_id"]:
        father = conn.execute(
            "SELECT surname FROM individuals WHERE id = ?", (child_link["husband_id"],)
        ).fetchone()
        father_surname = father["surname"] if father else None

    return {
        "given_names": row["given_names"],
        "surname": row["surname"],
        "birth_year": year_of(row["birth_date_sort"]),
        "birth_place": row["birth_place"],
        "death_year": year_of(row["death_date_sort"]),
        "death_place": row["death_place"],
        "father_surname": father_surname,
    }


@router.get("/{individual_id}/research-links")
def research_links(individual_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    row = _individual_or_404(conn, individual_id)
    facts = _facts(conn, row)
    return {"facts": facts, "links": uk_sources.build_links(facts)}


def _chain_step(row: dict) -> dict:
    parts = [row["given_names"], row["surname"]]
    name = " ".join(p for p in parts if p) or "(unknown)"
    return {
        "id": row["id"],
        "name": name,
        "birth_date_raw": row["birth_date_raw"],
        "birth_year": year_of(row["birth_date_sort"]),
        "birth_place": row["birth_place"],
        "death_date_raw": row["death_date_raw"],
        "death_year": year_of(row["death_date_sort"]),
        "generation": row["generation"],
        "has_citation": row["has_citation"],
        "citations": row["citations"],
    }


@router.get("/{individual_id}/patriline")
def individual_patriline(individual_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _individual_or_404(conn, individual_id)
    chain = [_chain_step(r) for r in get_patriline(conn, individual_id)]
    return {"chain": chain}
