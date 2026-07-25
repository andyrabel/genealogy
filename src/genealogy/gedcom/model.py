"""Generic GEDCOM tag-tree model.

This is intentionally schema-agnostic: it represents any GEDCOM 5.5.1 file
as a tree of (level, tag, pointer, value) nodes without needing to know the
meaning of every tag. That genericity is what makes lossless round-trip
export possible -- vendor-specific tags (e.g. Family Tree for Windows'
``_UID``, ``_MDATE``, etc.) survive automatically because the parser never
has to recognize them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GedcomNode:
    """A single GEDCOM line (level >= 1) and its children.

    ``value`` holds the line's value exactly as it appears after CONC/CONT
    lines have been merged in (CONC with no separator, CONT with "\n").
    If the value is a pointer (e.g. ``@F1@``), it is stored verbatim in
    ``value`` -- callers that need to resolve it can check with
    :func:`is_pointer`.
    """

    level: int
    tag: str
    value: str | None = None
    children: list[GedcomNode] = field(default_factory=list)

    def is_pointer(self) -> bool:
        return bool(self.value) and self.value.startswith("@") and self.value.endswith("@")

    def sub(self, tag: str) -> GedcomNode | None:
        """First direct child with the given tag, if any."""
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def sub_all(self, tag: str) -> list[GedcomNode]:
        return [child for child in self.children if child.tag == tag]


@dataclass
class GedcomRecord:
    """A top-level (level 0) GEDCOM record, e.g. ``0 @I1@ INDI``."""

    record_type: str
    xref_id: str | None
    value: str | None = None
    children: list[GedcomNode] = field(default_factory=list)
    sort_order: int = 0

    def sub(self, tag: str) -> GedcomNode | None:
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def sub_all(self, tag: str) -> list[GedcomNode]:
        return [child for child in self.children if child.tag == tag]


@dataclass
class GedcomDocument:
    """A full parsed GEDCOM file: an ordered list of records."""

    records: list[GedcomRecord] = field(default_factory=list)
    encoding: str = "utf-8"

    def by_type(self, record_type: str) -> list[GedcomRecord]:
        return [r for r in self.records if r.record_type == record_type]

    def by_xref(self, xref_id: str) -> GedcomRecord | None:
        for r in self.records:
            if r.xref_id == xref_id:
                return r
        return None
