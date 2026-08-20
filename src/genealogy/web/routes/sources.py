from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.db import edits
from genealogy.db.edits import NotFoundError
from genealogy.web.deps import get_conn
from genealogy.web.schemas import CitationIn, SourceIn

router = APIRouter(prefix="/api", tags=["sources"])


def _source_or_404(conn: sqlite3.Connection, source_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="source not found")
    return row


def _source_detail(conn: sqlite3.Connection, source: sqlite3.Row) -> dict:
    citations = []
    for c in conn.execute("SELECT * FROM citations WHERE source_id = ?", (source["id"],)):
        target = None
        if c["individual_id"]:
            indi = conn.execute(
                "SELECT id, given_names, surname FROM individuals WHERE id = ?", (c["individual_id"],)
            ).fetchone()
            if indi:
                target = {"type": "individual", "id": indi["id"], "name": f'{indi["given_names"] or ""} {indi["surname"] or ""}'.strip()}
        elif c["event_id"]:
            event = conn.execute(
                "SELECT id, event_type, owner_type, owner_id FROM events WHERE id = ?", (c["event_id"],)
            ).fetchone()
            if event:
                target = {
                    "type": "event",
                    "id": event["id"],
                    "event_type": event["event_type"],
                    "owner_type": event["owner_type"],
                    "owner_id": event["owner_id"],
                }
        citations.append(
            {"id": c["id"], "page": c["page"], "quality": c["quality"], "note": c["note"], "target": target}
        )
    return {
        "id": source["id"],
        "xref_id": source["xref_id"],
        "title": source["title"],
        "author": source["author"],
        "publication_info": source["publication_info"],
        "repository_note": source["repository_note"],
        "url": source["url"],
        "citations": citations,
    }


@router.get("/sources")
def list_sources(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    rows = conn.execute("SELECT * FROM sources ORDER BY title IS NULL, title").fetchall()
    return {"results": [dict(r) for r in rows]}


@router.get("/sources/{source_id}")
def get_source(source_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _source_detail(conn, _source_or_404(conn, source_id))


@router.post("/sources", status_code=201)
def create_source(body: SourceIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    source_id = edits.create_source(conn, **body.model_dump())
    return _source_detail(conn, _source_or_404(conn, source_id))


@router.put("/sources/{source_id}")
def update_source(source_id: int, body: SourceIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _source_or_404(conn, source_id)
    edits.update_source(conn, source_id, **body.model_dump())
    return _source_detail(conn, _source_or_404(conn, source_id))


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    _source_or_404(conn, source_id)
    edits.delete_source(conn, source_id)


@router.post("/citations", status_code=201)
def add_citation(body: CitationIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        citation_id = edits.add_citation(
            conn,
            source_id=body.source_id,
            event_id=body.event_id,
            individual_id=body.individual_id,
            page=body.page,
            quality=body.quality,
            note=body.note,
        )
    except (NotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dict(conn.execute("SELECT * FROM citations WHERE id = ?", (citation_id,)).fetchone())


@router.delete("/citations/{citation_id}", status_code=204)
def delete_citation(citation_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    try:
        edits.delete_citation(conn, citation_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
