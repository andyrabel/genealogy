"""Text-style genealogy reports: outline descendant charts and direct-line
(single lineage) reports, in the traditional numbered-outline format used
by desktop genealogy software.
"""

from __future__ import annotations

import sqlite3
from collections import deque

from fastapi import APIRouter, Depends, HTTPException

from genealogy.web.deps import get_conn
from genealogy.web.serialize import individual_summary, year_of

router = APIRouter(prefix="/api/reports", tags=["reports"])

MAX_GENERATIONS = 25


def _individual_or_404(conn: sqlite3.Connection, individual_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM individuals WHERE id = ?", (individual_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="individual not found")
    return row


def _unions(conn: sqlite3.Connection, individual_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM families WHERE husband_id = ? OR wife_id = ? "
        "ORDER BY marriage_date_sort IS NULL, marriage_date_sort, id",
        (individual_id, individual_id),
    ).fetchall()


def _children(conn: sqlite3.Connection, family_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT i.* FROM family_children fc JOIN individuals i ON i.id = fc.child_id "
        "WHERE fc.family_id = ? ORDER BY fc.sort_order",
        (family_id,),
    ).fetchall()


def _build_descendant_node(
    conn: sqlite3.Connection, row: sqlite3.Row, generation: int, ancestry: frozenset[int]
) -> dict:
    node = individual_summary(row)
    node["generation"] = generation

    if row["id"] in ancestry or generation >= MAX_GENERATIONS:
        node["unions"] = []
        return node

    ancestry = ancestry | {row["id"]}
    fams = _unions(conn, row["id"])
    unions = []
    for i, fam in enumerate(fams):
        spouse_id = fam["wife_id"] if fam["husband_id"] == row["id"] else fam["husband_id"]
        spouse_row = (
            conn.execute("SELECT * FROM individuals WHERE id = ?", (spouse_id,)).fetchone()
            if spouse_id is not None
            else None
        )
        children = [
            _build_descendant_node(conn, child_row, generation + 1, ancestry)
            for child_row in _children(conn, fam["id"])
        ]
        unions.append(
            {
                "family_id": fam["id"],
                "spouse": individual_summary(spouse_row) if spouse_row is not None else None,
                "marriage_date_raw": fam["marriage_date_raw"],
                "marriage_year": year_of(fam["marriage_date_sort"]),
                "marriage_place": fam["marriage_place"],
                "ordinal": i + 1,
                "total_unions": len(fams),
                "children": children,
            }
        )
    node["unions"] = unions
    return node


@router.get("/descendants/{individual_id}")
def descendants_outline(individual_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    root = _individual_or_404(conn, individual_id)
    return {"root": _build_descendant_node(conn, root, 1, frozenset())}


def _descendant_path(conn: sqlite3.Connection, ancestor_id: int, descendant_id: int) -> list[int] | None:
    """BFS down the descendant tree from `ancestor_id` to `descendant_id`,
    returning the chain of individual ids (inclusive of both ends), or
    None if `descendant_id` isn't reachable that way."""
    if ancestor_id == descendant_id:
        return [ancestor_id]

    parent_of: dict[int, int] = {}
    queue: deque[int] = deque([ancestor_id])
    seen = {ancestor_id}

    while queue:
        pid = queue.popleft()
        for fam in _unions(conn, pid):
            for child in _children(conn, fam["id"]):
                cid = child["id"]
                if cid in seen:
                    continue
                seen.add(cid)
                parent_of[cid] = pid
                if cid == descendant_id:
                    path = [cid]
                    while path[-1] != ancestor_id:
                        path.append(parent_of[path[-1]])
                    path.reverse()
                    return path
                queue.append(cid)

    return None


@router.get("/direct-line")
def direct_line(
    from_id: int, to_id: int, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    _individual_or_404(conn, from_id)
    _individual_or_404(conn, to_id)

    path_ids = _descendant_path(conn, from_id, to_id)
    if path_ids is None:
        raise HTTPException(
            status_code=404, detail="no direct descendant line found between these two people"
        )

    steps = []
    for i, pid in enumerate(path_ids):
        row = _individual_or_404(conn, pid)
        step = individual_summary(row)
        step["generation"] = i + 1
        step["spouse"] = None
        step["marriage_date_raw"] = None
        step["marriage_year"] = None
        step["marriage_place"] = None

        if i + 1 < len(path_ids):
            child_id = path_ids[i + 1]
            fam = conn.execute(
                "SELECT f.* FROM families f JOIN family_children fc ON fc.family_id = f.id "
                "WHERE fc.child_id = ? AND (f.husband_id = ? OR f.wife_id = ?)",
                (child_id, pid, pid),
            ).fetchone()
            if fam is not None:
                spouse_id = fam["wife_id"] if fam["husband_id"] == pid else fam["husband_id"]
                if spouse_id is not None:
                    spouse_row = conn.execute(
                        "SELECT * FROM individuals WHERE id = ?", (spouse_id,)
                    ).fetchone()
                    step["spouse"] = individual_summary(spouse_row)
                step["marriage_date_raw"] = fam["marriage_date_raw"]
                step["marriage_year"] = year_of(fam["marriage_date_sort"])
                step["marriage_place"] = fam["marriage_place"]

        steps.append(step)

    return {"steps": steps}
