from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import init_db
from api.routes import datasets, experiments, judge_routes, projects, reports, runs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Eval", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projects.router)
    app.include_router(datasets.router)
    app.include_router(runs.router)
    app.include_router(judge_routes.router)
    app.include_router(reports.router)
    app.include_router(experiments.router)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "service": "rag-eval-api"}

    return app


app = create_app()
