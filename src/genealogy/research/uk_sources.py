"""URL builders for free UK genealogical record search sites.

No scraping, no automated form submission: these just open each site's own
search page in a new tab. Query parameters are only pre-filled where a
site's search is a stable, stateless GET -- confirmed by inspecting each
site's actual search form before writing this module. Two shapes came up:

- FreeBMD's search form posts multipart/form-data with obscure session
  state (`sq`, `pgno`, `s_surname`/`s_given` shadow fields); a bare GET
  with the same field names just re-renders the empty form.
- FreeCEN and FreeREG are Rails apps whose search forms are protected by a
  per-session `authenticity_token` CSRF field, so a static link can't
  submit a valid search at all.
- GRO's index search requires a signed-in account.

None of those four can be pre-filled without effectively scraping a
session first, which this project deliberately avoids (see README). They
link to the plain search page instead; the research panel shows the
person's facts alongside so filling the form by hand takes seconds.
National Archives Discovery is the one exception: its results page is a
stable, bookmarkable GET URL, so it gets a true pre-filled deep link.
"""

from __future__ import annotations

from urllib.parse import urlencode


def _discovery_url(facts: dict) -> str:
    name = " ".join(p for p in (facts.get("given_names"), facts.get("surname")) if p)
    params = {"_q": name or ""}
    if facts.get("birth_year"):
        params["_sd"] = str(facts["birth_year"])
    if facts.get("death_year"):
        params["_ed"] = str(facts["death_year"])
    elif facts.get("birth_year"):
        params["_ed"] = str(int(facts["birth_year"]) + 100)
    return f"https://discovery.nationalarchives.gov.uk/results/r?{urlencode(params)}"


SOURCES = [
    {
        "key": "freebmd",
        "label": "FreeBMD",
        "description": (
            "Civil registration index of births, marriages and deaths in "
            "England & Wales, 1837 onward."
        ),
        "prefilled": False,
        "build": lambda facts: "https://www.freebmd.org.uk/cgi/search.pl",
    },
    {
        "key": "freecen",
        "label": "FreeCEN",
        "description": (
            "Transcribed census returns for England, Wales, Scotland and "
            "the Channel Islands."
        ),
        "prefilled": False,
        "build": lambda facts: "https://www.freecen.org.uk/search_queries/new",
    },
    {
        "key": "freereg",
        "label": "FreeREG",
        "description": (
            "Parish baptism, marriage and burial registers -- often the "
            "only record before civil registration began in 1837, so "
            "especially useful for extending the patriline further back."
        ),
        "prefilled": False,
        "build": lambda facts: "https://www.freereg.org.uk/search_queries/new",
    },
    {
        "key": "gro",
        "label": "GRO index",
        "description": (
            "Official General Register Office birth and death indexes "
            "(1837-1934/1957). A free account is required to search."
        ),
        "prefilled": False,
        "build": lambda facts: "https://www.gro.gov.uk/gro/content/certificates/indexes_search.asp",
    },
    {
        "key": "discovery",
        "label": "National Archives Discovery",
        "description": "Catalogue of records held by The National Archives and other UK archives.",
        "prefilled": True,
        "build": _discovery_url,
    },
]


def build_links(facts: dict) -> list[dict]:
    """`facts` may include given_names, surname, birth_year, birth_place,
    death_year, death_place, father_surname -- only birth_year/death_year/
    given_names/surname are currently used by any builder, but the fuller
    set is accepted so callers can pass the same dict they display in the
    panel's facts recap."""
    return [
        {
            "key": s["key"],
            "label": s["label"],
            "description": s["description"],
            "prefilled": s["prefilled"],
            "url": s["build"](facts),
        }
        for s in SOURCES
    ]
