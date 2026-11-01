import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from cryptolab.config import Settings
from cryptolab.models import Interval, Symbol
from cryptolab.storage import Store


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    store = Store(settings.database_path)

    @asynccontextmanager
    async def lifespan(app):
        store.migrate()
        yield

    app = FastAPI(title="CryptoLab · API local de pesquisa", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return JSONResponse(status_code=503, content={"detail": "Armazenamento indisponível. Verifique o backend local."})

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "public_read_only", "live_trading_enabled": False,
                "private_account_connected": False, "worker": store.status()}

    @app.get("/api/v1/market")
    def market(symbol: Symbol = "BTCUSDT", interval: Interval = "60"):
        snapshot = store.load(symbol, interval)
        if snapshot is None:
            raise HTTPException(503, "Sem dados coletados. Inicie o worker e aguarde a primeira coleta.")
        now = int(time.time() * 1000)
        age = (now - snapshot.source_time_ms) / 1000
        stale = age < -5 or age > settings.stale_after_seconds
        return {**snapshot.model_dump(mode="json"), "served_at_ms": now,
                "age_seconds": max(0, age), "stale": stale,
                "stale_after_seconds": settings.stale_after_seconds, "live_trading_enabled": False}

    return app


app = create_app()
