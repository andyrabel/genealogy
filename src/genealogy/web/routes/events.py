from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from genealogy.db import edits
from genealogy.db.edits import NotFoundError
from genealogy.web.deps import get_conn
from genealogy.web.schemas import EventIn, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])


class OwnedEventIn(EventIn):
    owner_type: str  # "INDI" or "FAM"
    owner_id: int


@router.post("", status_code=201)
def add_event(body: OwnedEventIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if body.owner_type not in ("INDI", "FAM"):
        raise HTTPException(status_code=400, detail="owner_type must be INDI or FAM")
    try:
        event_id = edits.add_event(
            conn,
            body.owner_type,
            body.owner_id,
            body.event_type,
            date_raw=body.date_raw,
            place=body.place,
            note=body.note,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dict(conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())


@router.put("/{event_id}")
def update_event(event_id: int, body: EventUpdate, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        edits.update_event(conn, event_id, date_raw=body.date_raw, place=body.place, note=body.note)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dict(conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    try:
        edits.delete_event(conn, event_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
