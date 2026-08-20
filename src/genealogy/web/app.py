"""FastAPI app factory for the local genealogy viewer/editor."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from genealogy.web.routes import events, families, individuals, reports, research, sources, tree

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: str | Path) -> FastAPI:
    app = FastAPI(title="Genealogy")
    app.state.db_path = Path(db_path)

    app.include_router(individuals.router)
    app.include_router(families.router)
    app.include_router(events.router)
    app.include_router(sources.router)
    app.include_router(tree.router)
    app.include_router(reports.router)
    app.include_router(research.router)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
