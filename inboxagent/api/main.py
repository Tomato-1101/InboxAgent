"""FastAPI アプリ本体。/health と、ビルド済みフロント(frontend/dist)の配信。

新着ポーリング(APScheduler)・各ルータは後続フェーズで追加する。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import get_settings
from ..db import init_db
from .routes import router

_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_DIST_DIR = _PROJECT_DIR / "frontend" / "dist"

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    global _scheduler
    if settings.poll_enabled:
        from apscheduler.schedulers.background import BackgroundScheduler
        from ..service import poll_tick

        _scheduler = BackgroundScheduler(daemon=True)
        # 取り込みは無料・AI分析は auto_analyze_enabled(既定OFF)のときだけ走る。
        _scheduler.add_job(poll_tick, "interval",
                           seconds=settings.poll_interval_seconds,
                           id="poll", max_instances=1, coalesce=True)
        _scheduler.start()
    try:
        yield
    finally:
        if _scheduler:
            _scheduler.shutdown(wait=False)


app = FastAPI(title="InboxAgent", version=__version__, lifespan=lifespan)


# ローカル専用 API。無認証なので、他サイトからの CSRF と DNS rebinding を
# Host/Origin の検証で塞ぐ（Vite dev は localhost:5173 からの Origin なので通る）。
_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _hostname(value: str) -> str:
    """"host:port" や "http://host:port" からホスト名だけを取り出す。"""
    v = value.split("://", 1)[-1].split("/", 1)[0]
    if v.startswith("["):          # IPv6 は [::1]:8020 形式
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if ":" in v else v


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    if _hostname(request.headers.get("host", "")) not in _LOCAL_HOSTNAMES:
        return JSONResponse({"detail": "ローカル以外のホスト名は許可されていません"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and _hostname(origin) not in _LOCAL_HOSTNAMES:
        return JSONResponse({"detail": "許可されていない Origin です"}, status_code=403)
    return await call_next(request)


app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "InboxAgent", "version": __version__}


# ビルド済みフロントがあれば配信（無ければ /health のみ動く）。
if _DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_DIST_DIR / "index.html")
