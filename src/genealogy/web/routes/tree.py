from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.web.deps import get_conn
from genealogy.web.serialize import year_of

router = APIRouter(prefix="/api/tree", tags=["tree"])


def _node(row: sqlite3.Row, *, is_spouse: bool = False) -> dict:
    parts = [row["given_names"], row["surname"]]
    name = " ".join(p for p in parts if p) or "(unknown)"
    return {
        "id": row["id"],
        "name": name,
        "sex": row["sex"],
        "birth_year": year_of(row["birth_date_sort"]),
        "death_year": year_of(row["death_date_sort"]),
        "is_living": bool(row["is_living"]),
        "is_spouse": is_spouse,
    }


@router.get("/{individual_id}")
def get_tree(
    individual_id: int,
    direction: str = "ancestors",
    generations: int = 4,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if direction not in ("ancestors", "descendants"):
        raise HTTPException(status_code=400, detail="direction must be 'ancestors' or 'descendants'")
    generations = max(1, min(generations, 10))

    root = conn.execute("SELECT * FROM individuals WHERE id = ?", (individual_id,)).fetchone()
    if root is None:
        raise HTTPException(status_code=404, detail="individual not found")

    nodes: dict[int, dict] = {root["id"]: _node(root)}
    edges: list[dict] = []
    frontier = [root["id"]]

    for _ in range(generations):
        next_frontier: list[int] = []

        if direction == "ancestors":
            for person_id in frontier:
                link = conn.execute(
                    "SELECT f.* FROM family_children fc JOIN families f ON f.id = fc.family_id "
                    "WHERE fc.child_id = ? LIMIT 1",
                    (person_id,),
                ).fetchone()
                if link is None:
                    continue
                for parent_id in (link["husband_id"], link["wife_id"]):
                    if parent_id is None:
                        continue
                    edges.append({"from": parent_id, "to": person_id, "type": "parent"})
                    if parent_id not in nodes:
                        parent_row = conn.execute(
                            "SELECT * FROM individuals WHERE id = ?", (parent_id,)
                        ).fetchone()
                        nodes[parent_id] = _node(parent_row)
                        next_frontier.append(parent_id)
        else:
            for person_id in frontier:
                for fam in conn.execute(
                    "SELECT * FROM families WHERE husband_id = ? OR wife_id = ?",
                    (person_id, person_id),
                ):
                    spouse_id = fam["wife_id"] if fam["husband_id"] == person_id else fam["husband_id"]
                    if spouse_id is not None and spouse_id not in nodes:
                        spouse_row = conn.execute(
                            "SELECT * FROM individuals WHERE id = ?", (spouse_id,)
                        ).fetchone()
                        nodes[spouse_id] = _node(spouse_row, is_spouse=True)
                        edges.append({"from": person_id, "to": spouse_id, "type": "spouse"})

                    for child in conn.execute(
                        "SELECT i.* FROM family_children fc JOIN individuals i ON i.id = fc.child_id "
                        "WHERE fc.family_id = ? ORDER BY fc.sort_order",
                        (fam["id"],),
                    ):
                        edges.append({"from": person_id, "to": child["id"], "type": "parent"})
                        if child["id"] not in nodes:
                            nodes[child["id"]] = _node(child)
                            next_frontier.append(child["id"])

        frontier = next_frontier
        if not frontier:
            break

    return {
        "root_id": root["id"],
        "direction": direction,
        "nodes": list(nodes.values()),
        "edges": edges,
    }
