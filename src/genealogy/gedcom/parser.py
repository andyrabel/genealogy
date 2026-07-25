"""Parse GEDCOM 5.5.1 text into a generic :class:`GedcomDocument` tree.

The parser does not special-case individual tags (aside from CONC/CONT,
which are a line-continuation mechanism rather than real structure). Every
other tag -- standard or vendor-specific -- becomes a node, which is what
makes lossless export possible later.
"""

from __future__ import annotations

import re

from genealogy.gedcom.encoding import decode_gedcom
from genealogy.gedcom.model import GedcomDocument, GedcomNode, GedcomRecord

_LINE_RE = re.compile(
    r"^(?P<level>\d+)"
    r"(?: (?P<xref>@[^@\s]+@))?"
    r"(?: (?P<tag>[A-Za-z0-9_]+))?"
    r"(?: (?P<value>.*))?$"
)


class GedcomParseError(ValueError):
    pass


def parse_gedcom_bytes(raw: bytes) -> GedcomDocument:
    """Decode raw file bytes (detecting charset from BOM / HEAD.CHAR) and parse."""
    text, encoding = decode_gedcom(raw)
    doc = parse_gedcom(text)
    doc.encoding = encoding
    return doc


def parse_gedcom(text: str) -> GedcomDocument:
    document = GedcomDocument()
    # Container is either a GedcomRecord (level 0) or GedcomNode (level >=1).
    stack: list[tuple[int, GedcomRecord | GedcomNode]] = []
    last_created: GedcomRecord | GedcomNode | None = None
    sort_order = 0

    lines = text.splitlines()
    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue

        match = _LINE_RE.match(line)
        if not match or match.group("tag") is None:
            raise GedcomParseError(f"Malformed GEDCOM line {lineno}: {raw_line!r}")

        level = int(match.group("level"))
        xref = match.group("xref")
        tag = match.group("tag")
        value = match.group("value")

        if tag.upper() in ("CONT", "CONC"):
            if last_created is None:
                raise GedcomParseError(
                    f"{tag} on line {lineno} has no preceding line to continue"
                )
            addition = value or ""
            separator = "\n" if tag.upper() == "CONT" else ""
            last_created.value = (last_created.value or "") + separator + addition
            continue

        if level == 0:
            record = GedcomRecord(
                record_type=tag,
                xref_id=xref,
                value=value,
                sort_order=sort_order,
            )
            sort_order += 1
            document.records.append(record)
            stack = [(0, record)]
            last_created = record
            continue

        # level >= 1: attach under the nearest open ancestor at level-1.
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            raise GedcomParseError(
                f"Line {lineno} at level {level} has no parent (bad level nesting)"
            )
        parent_level, parent = stack[-1]
        if level != parent_level + 1:
            # Tolerate skipped levels from malformed exports rather than
            # aborting the whole import; attach to nearest ancestor anyway.
            pass

        node = GedcomNode(level=level, tag=tag, value=value)
        parent.children.append(node)
        stack.append((level, node))
        last_created = node

    return document
