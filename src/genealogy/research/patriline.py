"""Direct male-line (patriline) ancestry: father, father's father, and so
on, via `families.husband_id` / `family_children`.

Pure read-only queries over a connection, like `db/edits.py`'s reads --
deliberately kept independent of the web layer so it's directly unit
testable and reusable outside FastAPI.
"""

from __future__ import annotations

import sqlite3


def get_patriline(conn: sqlite3.Connection, individual_id: int) -> list[dict]:
    """Return the chain from `individual_id` up through consecutive fathers,
    starting at generation 0 (the individual themself). Stops at the first
    ancestor with no recorded father -- the current edge of the known line.
    """
    rows = conn.execute(
        """
        WITH RECURSIVE patriline(id, generation) AS (
            SELECT ?, 0
            UNION ALL
            SELECT f.husband_id, patriline.generation + 1
            FROM patriline
            JOIN family_children fc ON fc.child_id = patriline.id
            JOIN families f ON f.id = fc.family_id
            WHERE f.husband_id IS NOT NULL
        )
        SELECT i.*, patriline.generation
        FROM patriline
        JOIN individuals i ON i.id = patriline.id
        ORDER BY patriline.generation
        """,
        (individual_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "xref_id": row["xref_id"],
            "given_names": row["given_names"],
            "surname": row["surname"],
            "birth_date_raw": row["birth_date_raw"],
            "birth_date_sort": row["birth_date_sort"],
            "birth_place": row["birth_place"],
            "death_date_raw": row["death_date_raw"],
            "death_date_sort": row["death_date_sort"],
            "generation": row["generation"],
            "citations": (citations := _citations(conn, row["id"])),
            "has_citation": len(citations) > 0,
        }
        for row in rows
    ]


def _citations(conn: sqlite3.Connection, individual_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.title AS source_title, c.page AS page
        FROM citations c
        LEFT JOIN sources s ON s.id = c.source_id
        WHERE c.individual_id = :id
           OR c.event_id IN (
               SELECT id FROM events
               WHERE owner_type = 'INDI' AND owner_id = :id AND event_type = 'BIRT'
           )
        """,
        {"id": individual_id},
    ).fetchall()
    return [{"source_title": row["source_title"], "page": row["page"]} for row in rows]
