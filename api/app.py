"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the HTTP delivery application."""
    app = FastAPI(title="findmy-bridge")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
