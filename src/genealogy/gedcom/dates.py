"""Best-effort GEDCOM date parsing for sort keys.

GEDCOM dates are free-ish text ("ABT 1850", "BET 1840 AND 1845",
"12 MAR 1875", "1850", ...). We don't need calendar-accurate parsing here --
only a stable, comparable sort key so the UI and gap analysis can order
people by approximate date. Unparseable dates simply produce no sort key.
"""

from __future__ import annotations

import re

_MONTHS = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

_QUALIFIERS = re.compile(
    r"^\s*(ABT|EST|CAL|BEF|AFT|BET|FROM|TO|INT)\b\.?\s*", re.IGNORECASE
)
_DATE_RE = re.compile(
    r"(?:(?P<day>\d{1,2})\s+)?(?:(?P<month>[A-Za-z]{3})\s+)?(?P<year>\d{3,4})"
)


def parse_gedcom_date(raw: str | None) -> str | None:
    """Return a "YYYY-MM-DD" (zero-padded where unknown) sort key, or None."""
    if not raw:
        return None

    text = raw.strip()
    # BET/FROM ranges: use the first date mentioned as the representative one.
    text = _QUALIFIERS.sub("", text)

    match = _DATE_RE.search(text)
    if not match:
        return None

    year = match.group("year").zfill(4)
    month = _MONTHS.get((match.group("month") or "").upper(), "00")
    day = (match.group("day") or "").zfill(2) if match.group("day") else "00"
    return f"{year}-{month}-{day}"
