# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local-first genealogy tool: import a GEDCOM file into SQLite, research and
edit the tree through a local web UI, and export back to valid GEDCOM at any
time. Everything runs on the user's own machine — no paid services, no
hosting required.

## Data privacy — read before touching `data/` or `.ged` files

This repository contains **only code**. Real genealogy data (GEDCOM files,
the SQLite database, anything derived from family data) belongs in `data/`,
which is gitignored entirely except `data/.gitkeep`. `*.ged`/`*.GED`/`*.db`
files are gitignored anywhere in the repo. **Never commit real genealogy
data.** The only GEDCOM fixture meant to be tracked is the fully fictional
`tests/fixtures/sample_gedcom.py`. Before any `git add`, double check no real
`.ged`/`.db` file has been staged.

## Commands

```bash
source scripts/dev.sh                          # create/activate .venv, install project + dev deps

genealogy import path/to/file.ged --db data/tree.db   # GEDCOM -> SQLite
genealogy export data/tree.db path/to/out.ged          # SQLite -> GEDCOM
genealogy serve --db data/tree.db                      # local web UI at http://127.0.0.1:8000

pytest                                          # run all tests
pytest tests/test_edits.py                      # run one test file
pytest tests/test_edits.py::test_name -v        # run one test
```

There is no build step for the frontend (vanilla JS + D3, vendored — no npm,
no bundler) and no configured linter/formatter in `pyproject.toml`.

## Architecture

The GEDCOM/database layer is a **two-layer store**, and this distinction
drives almost every design decision in `src/genealogy/db/`:

1. **Raw tree** (`gedcom_records` / `gedcom_nodes` tables) — a generic,
   lossless copy of every line in the imported file: level, tag, pointer,
   value, in original order. This is the source of truth for export, and
   it's schema-agnostic, so vendor-specific tags (e.g. things Family Tree
   for Windows might emit, like `_UID`) survive round-trip automatically
   without the parser needing to know what they mean.
2. **Normalized tables** (`individuals`, `families`, `family_children`,
   `events`, `sources`, `citations`, `notes`) — derived from the raw tree by
   `genealogy.db.normalize`, for fast querying and the web UI. These are
   fully rebuilt on every import and are **never hand-edited directly**.

The rule that follows from this: **all edits go through the raw GEDCOM
tree**, never the normalized tables directly, so round-trip export fidelity
is preserved. `genealogy.db.edits` is where every domain-level write lives —
each public function there mutates `gedcom_records`/`gedcom_nodes` via
`genealogy.db.tree_edit`, then calls `rebuild_normalized_tables` and commits,
so it's a complete, self-contained unit of work. The web API layer only ever
calls into `genealogy.db.edits`; it does not touch `tree_edit` or the
normalized tables' writes itself.

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
    normalize.py  raw tree -> normalized tables (full rebuild, not incremental)
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

Backend: Python 3.11+, stdlib `sqlite3` (no ORM — deliberate, since the
schema is small and fidelity-critical enough that direct SQL is worth more
than ORM convenience), FastAPI + Uvicorn.

Round-trip fidelity is the load-bearing correctness property of the whole
GEDCOM layer and is verified in `tests/test_roundtrip.py` (pure GEDCOM layer)
and `tests/test_importer.py` (through the database), both using the
synthetic fixture in `tests/fixtures/sample_gedcom.py`. Any change touching
`gedcom/parser.py`, `gedcom/writer.py`, or `db/importer.py`/`db/exporter.py`
should be checked against these tests specifically — a change that passes
`test_edits.py`/`test_api.py` but breaks round-trip fidelity has silently
introduced data loss on export.

## Roadmap context

Phase 1 (GEDCOM tree tool: parser/writer, SQLite storage, import/export CLI,
web UI for browsing/editing) is essentially complete. Phase 2 (UK research
assistant: FamilySearch API integration, URL builders for FreeBMD/FreeCEN/
FreeREG/National Archives Discovery, candidate-match review, auto-citations)
has not been started — `httpx` is already a dependency in anticipation of it.
