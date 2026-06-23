"""FastAPI アプリ本体。/health と、ビルド済みフロント(frontend/dist)の配信。

新着ポーリング(APScheduler)・各ルータは後続フェーズで追加する。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..db import init_db

_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_DIST_DIR = _PROJECT_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="InboxAgent", version=__version__, lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "InboxAgent", "version": __version__}


# ビルド済みフロントがあれば配信（無ければ /health のみ動く）。
if _DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_DIST_DIR / "index.html")
