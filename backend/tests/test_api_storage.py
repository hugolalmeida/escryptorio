import hashlib
import time

import pytest
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.config import Settings
from cryptolab.storage import canonical_dataset


def test_migrations_idempotent_and_hash(store, snapshot):
    store.migrate()
    store.save(snapshot)
    store.save(snapshot)
    loaded = store.load("BTCUSDT", "60")
    assert loaded == snapshot
    assert loaded.ticker.price.as_tuple() == snapshot.ticker.price.as_tuple()
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 1
        payload = db.execute("SELECT payload FROM datasets").fetchone()[0]
    assert hashlib.sha256(payload.encode()).hexdigest() == snapshot.dataset_id


def test_dataset_only_closed_candles(candles):
    before = canonical_dataset("BTCUSDT", "60", candles)
    opened = candles[-1].model_copy(update={"time": 1000000, "closed": False})
    assert canonical_dataset("BTCUSDT", "60", candles + [opened]) == before
    assert canonical_dataset("ETHUSDT", "60", candles)[0] != before[0]
    assert canonical_dataset("BTCUSDT", "15", candles)[0] != before[0]


def test_api_health_no_data_and_validation(settings):
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
        assert health["live_trading_enabled"] is False
        assert health["private_account_connected"] is False
        assert client.get("/api/v1/market").status_code == 503
        assert client.get("/api/v1/market?symbol=SOLUSDT").status_code == 422
        assert client.get("/api/v1/market?interval=1").status_code == 422
        assert client.get("/api/v1/market", headers={"host": "evil.invalid"}).status_code == 400
        assert client.post("/api/v1/market").status_code == 405
        assert client.post("/api/v1/orders", json={"side": "Buy"}).status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert set(paths) == {"/health", "/api/v1/market", "/api/v1/history/coverage",
            "/api/v1/history/jobs", "/api/v1/history/jobs/{job_id}", "/api/v1/history/jobs/{job_id}/{action}",
            "/api/v1/history/datasets", "/api/v1/history/datasets/{dataset_id}"}
        mutations = {path for path, verbs in paths.items() if set(verbs) != {"get"}}
        assert mutations == {"/api/v1/history/jobs", "/api/v1/history/jobs/{job_id}/{action}"}
        assert set(paths["/api/v1/history/jobs"]) == {"get", "post"}
        assert set(paths["/api/v1/history/jobs/{job_id}/{action}"]) == {"post"}


def test_api_decimal_timestamp_and_staleness(settings, store, snapshot, monkeypatch):
    store.save(snapshot)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/market")
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["ticker"]["price"] == "180.001"
        assert data["stale"] is False
        assert data["source_time_ms"] == snapshot.source_time_ms
        monkeypatch.setattr(time, "time", lambda: snapshot.source_time_ms / 1000 + 91)
        assert client.get("/api/v1/market").json()["stale"] is True
        monkeypatch.setattr(time, "time", lambda: snapshot.source_time_ms / 1000 - 10)
        assert client.get("/api/v1/market").json()["stale"] is True


def test_errors_preserve_last_good_timestamp(store, snapshot):
    store.save(snapshot)
    store.record_attempt(1000, None)
    store.record_attempt(2000, "BYBIT_UNAVAILABLE")
    assert store.load("BTCUSDT", "60").source_time_ms == snapshot.source_time_ms
    assert store.status()["last_success_ms"] == 1000
    assert store.status()["error_code"] == "BYBIT_UNAVAILABLE"


@pytest.mark.parametrize("flag", ["true", "1", "yes", "", "False "])
def test_live_flag_fails_closed(monkeypatch, flag):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", flag)
    with pytest.raises(RuntimeError, match="Execução real indisponível"):
        Settings.from_env()
