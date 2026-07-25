"""Shared row -> dict serialization helpers used by multiple route modules."""

from __future__ import annotations

import sqlite3


def display_name(row: sqlite3.Row) -> str:
    parts = [row["name_prefix"], row["given_names"], row["surname"], row["name_suffix"]]
    name = " ".join(p for p in parts if p)
    return name or "(unknown)"


def individual_summary(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "xref_id": row["xref_id"],
        "name": display_name(row),
        "given_names": row["given_names"],
        "surname": row["surname"],
        "sex": row["sex"],
        "birth_date_raw": row["birth_date_raw"],
        "birth_place": row["birth_place"],
        "death_date_raw": row["death_date_raw"],
        "death_place": row["death_place"],
        "is_living": bool(row["is_living"]),
    }
