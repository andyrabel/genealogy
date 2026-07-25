"""Command-line entry point for genealogy: import/export GEDCOM <-> SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from genealogy.db.connection import connect, init_db
from genealogy.db.exporter import export_gedcom_file
from genealogy.db.importer import import_gedcom_file

DEFAULT_DB = "data/tree.db"


def cmd_import(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    init_db(conn)
    document = import_gedcom_file(conn, args.gedcom_file)
    print(f"Imported {len(document.records)} records from {args.gedcom_file} into {db_path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    export_gedcom_file(conn, args.gedcom_file)
    print(f"Exported {args.db} to {args.gedcom_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genealogy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import a GEDCOM file into the database")
    import_parser.add_argument("gedcom_file", help="Path to the .ged file to import")
    import_parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    import_parser.set_defaults(func=cmd_import)

    export_parser = subparsers.add_parser("export", help="Export the database to a GEDCOM file")
    export_parser.add_argument("gedcom_file", help="Path to write the .ged file to")
    export_parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    export_parser.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
