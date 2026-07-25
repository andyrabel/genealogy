"""Shared helpers for comparing parsed GEDCOM trees in tests."""

from __future__ import annotations

from genealogy.gedcom.model import GedcomDocument, GedcomNode, GedcomRecord


def node_to_tuple(node: GedcomNode) -> tuple:
    return (node.level, node.tag, node.value, tuple(node_to_tuple(c) for c in node.children))


def record_to_tuple(record: GedcomRecord) -> tuple:
    return (
        record.record_type,
        record.xref_id,
        record.value,
        tuple(node_to_tuple(c) for c in record.children),
    )


def doc_to_tuple(document: GedcomDocument) -> tuple:
    return tuple(record_to_tuple(r) for r in document.records)
