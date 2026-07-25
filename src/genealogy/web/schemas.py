"""Request body models for the web API. Responses are plain dicts built
from sqlite rows -- a local single-user tool doesn't need a parallel set
of response schemas duplicating the DB shape."""

from __future__ import annotations

from pydantic import BaseModel


class IndividualIn(BaseModel):
    given_names: str | None = None
    surname: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    sex: str | None = None


class EventIn(BaseModel):
    event_type: str
    date_raw: str | None = None
    place: str | None = None
    note: str | None = None


class EventUpdate(BaseModel):
    date_raw: str | None = None
    place: str | None = None
    note: str | None = None


class FamilyCreate(BaseModel):
    husband_id: int | None = None
    wife_id: int | None = None


class SpouseUpdate(BaseModel):
    role: str  # "HUSB" or "WIFE"
    individual_id: int | None = None


class ChildIn(BaseModel):
    child_id: int


class MarriageUpdate(BaseModel):
    date_raw: str | None = None
    place: str | None = None


class SourceIn(BaseModel):
    title: str | None = None
    author: str | None = None
    publication_info: str | None = None
    repository_note: str | None = None


class CitationIn(BaseModel):
    source_id: int
    event_id: int | None = None
    individual_id: int | None = None
    page: str | None = None
    quality: str | None = None
    note: str | None = None
