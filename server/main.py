from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.db import init_db
from server.routers import (
    agent,
    chat_proxy,
    chats,
    config,
    files,
    health,
    knowledge,
    memories,
    models,
    tasks,
)


WEB_DIST_DIR = Path(__file__).resolve().parent.parent / "dist"


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="MyOpenWeb Server", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(models.router)
    app.include_router(chat_proxy.router)
    app.include_router(agent.router)
    app.include_router(chats.router)
    app.include_router(memories.router)
    app.include_router(files.router)
    app.include_router(knowledge.router)
    app.include_router(tasks.router)

    # Serve the built H5 when present (single-container deploy); API routes
    # above take precedence, everything else falls through to the SPA.
    if WEB_DIST_DIR.exists():
        app.mount("/", StaticFiles(directory=WEB_DIST_DIR, html=True), name="web")
    return app


app = create_app()
