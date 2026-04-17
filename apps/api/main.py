"""FastAPI entrypoint. Routers mounted here."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import artifacts as artifacts_route
from src.routes import chat as chat_route
from src.routes import contexts as contexts_route
from src.routes import runs as runs_route

app = FastAPI(title="BetterLabs Research Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


# Routers — each module exposes a top-level `router`
app.include_router(runs_route.router)
app.include_router(chat_route.router)
app.include_router(artifacts_route.router)
app.include_router(contexts_route.router)
