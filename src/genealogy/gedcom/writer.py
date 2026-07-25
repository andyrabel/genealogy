"""Serialize a :class:`GedcomDocument` back to valid GEDCOM 5.5.1 text.

Values are re-wrapped into CONC (length-wrap) / CONT (embedded newline)
continuation lines as needed so long or multi-line values stay within the
255-character line length GEDCOM 5.5.1 specifies, regardless of how the
value was originally represented in the source file.
"""

from __future__ import annotations

from genealogy.gedcom.model import GedcomDocument, GedcomNode, GedcomRecord

MAX_LINE_LENGTH = 255


def write_gedcom(document: GedcomDocument) -> str:
    lines: list[str] = []
    for record in sorted(document.records, key=lambda r: r.sort_order):
        _emit_record(record, lines)
    return "\n".join(lines) + "\n"


def _emit_record(record: GedcomRecord, lines: list[str]) -> None:
    prefix = f"{record.xref_id} {record.record_type}" if record.xref_id else record.record_type
    _emit_value(0, prefix, record.value, lines)
    for child in record.children:
        _emit_node(child, lines)


def _emit_node(node: GedcomNode, lines: list[str]) -> None:
    _emit_value(node.level, node.tag, node.value, lines)
    for child in node.children:
        _emit_node(child, lines)


def _emit_value(level: int, prefix: str, value: str | None, lines: list[str]) -> None:
    if value is None:
        lines.append(f"{level} {prefix}")
        return

    segments = value.split("\n")
    _emit_wrapped(level, prefix, segments[0], lines)
    for segment in segments[1:]:
        _emit_wrapped(level + 1, "CONT", segment, lines)


def _emit_wrapped(level: int, prefix: str, text: str, lines: list[str]) -> None:
    base = f"{level} {prefix} "
    budget = max(MAX_LINE_LENGTH - len(base), 1)

    if len(text) <= budget:
        lines.append(f"{level} {prefix} {text}" if text else f"{level} {prefix} ")
        return

    lines.append(f"{level} {prefix} {text[:budget]}")
    remainder = text[budget:]

    conc_level = level + 1
    conc_budget = max(MAX_LINE_LENGTH - len(f"{conc_level} CONC "), 1)
    while remainder:
        chunk, remainder = remainder[:conc_budget], remainder[conc_budget:]
        lines.append(f"{conc_level} CONC {chunk}")
