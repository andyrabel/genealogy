# genealogy

A local-first genealogy tool: import a GEDCOM file into SQLite, research and
edit your tree through a local web UI, and export back to valid GEDCOM at
any time. Everything runs on your own machine — no paid services, no
hosting required.

## Data privacy

This repository contains **only code**. Your GEDCOM file, the SQLite
database, and anything derived from your family data belong in `data/`,
which is gitignored entirely (`data/.gitkeep` is the only tracked file in
that directory, just to preserve the folder in checkouts). `*.ged` files are
also gitignored anywhere in the repo. Never commit real genealogy data —
only the fixture in `tests/fixtures/sample_gedcom.py` (fully fictional data)
is meant to be tracked.

## Architecture

The GEDCOM/database layer (Phase 1's foundation) is a **two-layer store**:

1. **Raw tree** (`gedcom_records` / `gedcom_nodes` tables) — a generic,
   lossless copy of every line in the imported file: level, tag, pointer,
   value, in original order. This is the source of truth for export, and
   it's schema-agnostic, so vendor-specific tags (e.g. things Family Tree
   for Windows might emit, like `_UID`) survive round-trip automatically
   without the parser needing to know what they mean.
2. **Normalized tables** (`individuals`, `families`, `family_children`,
   `events`, `sources`, `citations`, `notes`) — derived from the raw tree
   by `genealogy.db.normalize`, for fast querying and the web UI. These are
   fully rebuilt on every import; they're never hand-edited directly.

```
src/genealogy/
  gedcom/
    model.py      GedcomNode / GedcomRecord / GedcomDocument (the tree)
    parser.py     GEDCOM text -> tree
    writer.py     tree -> GEDCOM text (CONC/CONT line wrapping)
    encoding.py   charset detection (ANSI/UTF-8/UTF-16, BOM + HEAD.CHAR)
    dates.py      best-effort date parsing for sort keys
  db/
    schema.sql    raw tree tables + normalized tables
    connection.py sqlite3 connection/init helper
    importer.py   GEDCOM file/document -> raw tree tables
    normalize.py  raw tree -> normalized tables
    exporter.py   raw tree tables -> GedcomDocument -> GEDCOM text
    tree_edit.py  low-level read/write primitives on the raw tree
    edits.py      domain edits (individuals/families/events/sources), each
                   committing a raw-tree mutation + normalized-table rebuild
  web/
    app.py        FastAPI app factory, mounts the API + static frontend
    routes/       individuals/families/events/sources/tree JSON endpoints
    static/       vanilla JS + D3 frontend (no build step)
  cli.py          `genealogy import` / `genealogy export` / `genealogy serve`
```

Round-trip fidelity is verified in `tests/test_roundtrip.py` (pure GEDCOM
layer) and `tests/test_importer.py` (through the database), using a
synthetic fixture in `tests/fixtures/sample_gedcom.py`.

## Tech stack

- **Backend**: Python 3.12, stdlib `sqlite3` (no ORM — the schema is small
  and fidelity-critical enough that direct SQL is worth more than ORM
  convenience), FastAPI + Uvicorn for the local web UI. Edits always go
  through the raw GEDCOM tree (`genealogy.db.edits`), never the normalized
  tables directly, so round-trip export fidelity is preserved.
- **Frontend**: vanilla JS + D3.js (vendored, no CDN) for the pedigree
  diagram, served as static files by FastAPI — no Node build step needed,
  which keeps the dev workflow simple under WSL.
- **Research module** (Phase 2): `httpx` for the FamilySearch API; plain URL
  builders (no scraping) for FreeBMD/FreeCEN/FreeREG/National Archives
  Discovery, since those are search-form sites without open APIs.

## Setup (WSL / Oracle Linux 9 or any Linux)

```bash
source scripts/dev.sh   # creates .venv, installs the project + dev deps
```

## Usage

```bash
# Import your GEDCOM export from Family Tree for Windows
genealogy import /path/to/your-export.ged --db data/tree.db

# Browse and edit the tree at http://127.0.0.1:8000
genealogy serve --db data/tree.db

# Export back to GEDCOM at any time
genealogy export data/tree.db /path/to/output.ged
```

## Running tests

```bash
pytest
```

## Roadmap

**Phase 1 — GEDCOM tree tool**
- [x] GEDCOM 5.5.1 parser/writer with round-trip fidelity
- [x] SQLite raw-tree + normalized schema
- [x] Import/export CLI
- [x] FastAPI local web UI: pedigree/family tree diagram
- [x] Search individuals by name/date/place
- [x] Add/edit people, relationships, events, sources through the UI
- [ ] Data-quality flags (missing dates, orphaned records, duplicates)
- [ ] Gap analysis view (most-promising-to-research-next ranking)

**Phase 2 — UK research assistant**
- [ ] FamilySearch API integration (search + hints)
- [ ] URL builders for FreeBMD / FreeCEN / FreeREG / National Archives Discovery
- [ ] Candidate-match review screen (approve/reject before it touches the tree)
- [ ] Auto-generated source citations on approval
