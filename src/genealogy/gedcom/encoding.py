"""Character-encoding detection for GEDCOM files.

Old desktop genealogy software (Family Tree for Windows included) commonly
exports GEDCOM in Windows ANSI (cp1252) or UTF-16, not UTF-8. GEDCOM 5.5.1
declares the encoding in the ``HEAD.CHAR`` line, but that line itself has to
be read before we know how to decode the file -- so we sniff a BOM first,
and otherwise do a lossless latin-1 pre-pass just to locate the CHAR value.
"""

from __future__ import annotations

_CHARSET_MAP = {
    "ANSI": "cp1252",
    "ASCII": "ascii",
    "UTF-8": "utf-8",
    "UTF8": "utf-8",
    "UNICODE": "utf-16",
}


def detect_encoding(raw: bytes) -> str:
    """Return a Python codec name for the given raw GEDCOM file bytes."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # No BOM: latin-1 never raises, and is byte-preserving enough to find
    # the "1 CHAR <value>" line regardless of the file's real encoding
    # (ASCII-range bytes for tags/structure are stable across all of these
    # charsets).
    preview = raw[:4096].decode("latin-1", errors="replace")
    for line in preview.splitlines():
        stripped = line.strip()
        if stripped.startswith("1 CHAR "):
            declared = stripped[len("1 CHAR ") :].strip().upper()
            return _CHARSET_MAP.get(declared, "cp1252")

    # No HEAD.CHAR found (malformed or truncated preview) -- default to
    # the most common legacy export encoding.
    return "cp1252"


def decode_gedcom(raw: bytes) -> tuple[str, str]:
    """Decode raw GEDCOM bytes, returning (text, encoding_used)."""
    encoding = detect_encoding(raw)
    try:
        return raw.decode(encoding), encoding
    except UnicodeDecodeError:
        return raw.decode(encoding, errors="replace"), encoding
