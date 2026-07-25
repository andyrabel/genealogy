-- Genealogy database schema.
--
-- Two layers:
--   1. Raw tree (gedcom_records / gedcom_nodes): a generic, lossless copy of
--      every line in the imported GEDCOM file. This is the SOURCE OF TRUTH
--      for export -- it's what guarantees round-trip fidelity, including
--      vendor-specific tags this schema doesn't otherwise understand.
--   2. Normalized tables (individuals, families, ...): derived from the raw
--      tree by genealogy.db.normalize for fast querying and the web UI.
--      They are rebuilt from the tree, never hand-edited directly by import;
--      UI edits go through the app layer, which updates both layers.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Raw GEDCOM tree
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gedcom_records (
    id          INTEGER PRIMARY KEY,
    record_type TEXT NOT NULL,        -- INDI, FAM, SOUR, REPO, NOTE, OBJE, SUBM, HEAD, TRLR, ...
    xref_id     TEXT,                 -- original @I1@ / @F1@ / NULL for HEAD/TRLR
    value       TEXT,                 -- level-0 line value, if any (e.g. inline NOTE text)
    sort_order  INTEGER NOT NULL      -- preserves original file order for export
);

CREATE INDEX IF NOT EXISTS idx_gedcom_records_type ON gedcom_records(record_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_gedcom_records_xref ON gedcom_records(xref_id)
    WHERE xref_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS gedcom_nodes (
    id             INTEGER PRIMARY KEY,
    record_id      INTEGER NOT NULL REFERENCES gedcom_records(id) ON DELETE CASCADE,
    parent_node_id INTEGER REFERENCES gedcom_nodes(id) ON DELETE CASCADE,
    level          INTEGER NOT NULL,
    tag            TEXT NOT NULL,
    value          TEXT,              -- may itself be a pointer, e.g. "@S1@"
    sort_order     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gedcom_nodes_record ON gedcom_nodes(record_id);
CREATE INDEX IF NOT EXISTS idx_gedcom_nodes_parent ON gedcom_nodes(parent_node_id);
CREATE INDEX IF NOT EXISTS idx_gedcom_nodes_tag ON gedcom_nodes(tag);

-- ---------------------------------------------------------------------
-- Normalized tables (derived -- see genealogy.db.normalize)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS individuals (
    id              INTEGER PRIMARY KEY,
    record_id       INTEGER NOT NULL UNIQUE REFERENCES gedcom_records(id) ON DELETE CASCADE,
    xref_id         TEXT NOT NULL,
    given_names     TEXT,
    surname         TEXT,
    name_prefix     TEXT,
    name_suffix     TEXT,
    sex             TEXT,              -- M, F, U, X per GEDCOM
    birth_date_raw  TEXT,
    birth_date_sort TEXT,              -- normalized YYYY-MM-DD (or partial) for sorting/filtering
    birth_place     TEXT,
    death_date_raw  TEXT,
    death_date_sort TEXT,
    death_place     TEXT,
    is_living       INTEGER NOT NULL DEFAULT 0  -- heuristic: no death fact and no old birth date
);

CREATE INDEX IF NOT EXISTS idx_individuals_surname ON individuals(surname);
CREATE INDEX IF NOT EXISTS idx_individuals_birth_sort ON individuals(birth_date_sort);

CREATE TABLE IF NOT EXISTS families (
    id                  INTEGER PRIMARY KEY,
    record_id           INTEGER NOT NULL UNIQUE REFERENCES gedcom_records(id) ON DELETE CASCADE,
    xref_id             TEXT NOT NULL,
    husband_id          INTEGER REFERENCES individuals(id) ON DELETE SET NULL,
    wife_id             INTEGER REFERENCES individuals(id) ON DELETE SET NULL,
    marriage_date_raw   TEXT,
    marriage_date_sort  TEXT,
    marriage_place      TEXT
);

CREATE TABLE IF NOT EXISTS family_children (
    id          INTEGER PRIMARY KEY,
    family_id   INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    child_id    INTEGER NOT NULL REFERENCES individuals(id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(family_id, child_id)
);

-- Generic life events for both individuals and families (BIRT, DEAT, MARR,
-- RESI, OCCU, CHR, BURI, ...). Birth/death are also denormalized onto
-- `individuals` for fast common-case queries, but this table is the full
-- record of every event fact.
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY,
    owner_type   TEXT NOT NULL CHECK (owner_type IN ('INDI', 'FAM')),
    owner_id     INTEGER NOT NULL,   -- individuals.id or families.id depending on owner_type
    node_id      INTEGER REFERENCES gedcom_nodes(id) ON DELETE SET NULL,
    event_type   TEXT NOT NULL,      -- GEDCOM tag: BIRT, DEAT, MARR, ...
    date_raw     TEXT,
    date_sort    TEXT,
    place        TEXT,
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_owner ON events(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY,
    record_id       INTEGER NOT NULL UNIQUE REFERENCES gedcom_records(id) ON DELETE CASCADE,
    xref_id         TEXT NOT NULL,
    title           TEXT,
    author          TEXT,
    publication_info TEXT,
    repository_note TEXT
);

CREATE TABLE IF NOT EXISTS citations (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    node_id       INTEGER REFERENCES gedcom_nodes(id) ON DELETE CASCADE,
    event_id      INTEGER REFERENCES events(id) ON DELETE CASCADE,
    individual_id INTEGER REFERENCES individuals(id) ON DELETE CASCADE,
    page          TEXT,
    quality       TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY,
    record_id  INTEGER UNIQUE REFERENCES gedcom_records(id) ON DELETE CASCADE,
    text       TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- App-level bookkeeping (not GEDCOM data)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS import_log (
    id           INTEGER PRIMARY KEY,
    source_file  TEXT NOT NULL,
    imported_at  TEXT NOT NULL DEFAULT (datetime('now')),
    record_count INTEGER NOT NULL
);
