"""Observabilidade somente leitura; fixtures sintéticas isoladas."""
from fastapi.testclient import TestClient
from cryptolab.api import create_app
from cryptolab.config import Settings
from cryptolab.paper.models import FillRecord, StateRecord, WalletSpec
from cryptolab.paper.storage import PaperStore
from test_paper_decisions import services, active, record
from test_paper_planner import setup_planner

TABLES = ("paper_wallets", "paper_events", "paper_heads", "paper_bindings", "paper_decisions",
          "paper_decision_clock", "paper_mark_evidence", "paper_execution_evidence",
          "monitor_signals", "monitor_runtime", "monitor_leases", "collection_status")

def contents(store):
    with store.connect() as db:
        return {t: [tuple(x) for x in db.execute("SELECT * FROM " + t)] for t in TABLES}

def test_empty_alerts_stable_and_no_writes(settings, store):
    before = contents(store)
    with TestClient(create_app(settings)) as client:
        first = client.get("/api/v1/paper/operations/overview")
        second = client.get("/api/v1/paper/operations/overview")
        assert first.status_code == 200
        data = first.json()["data"]
        assert len(data["markets"]) == 8 and data["process_liveness"] == "UNKNOWN"
        assert data["financial_integrity"] == "UNKNOWN"
        assert len([a for a in data["alerts"] if a["code"] == "MARKET_SNAPSHOT_MISSING"]) == 8
        assert all(a["first_seen_at_ms"] is None for a in data["alerts"])
        assert {a["id"] for a in data["alerts"]} == {a["id"] for a in second.json()["data"]["alerts"]}
        assert client.post("/api/v1/paper/operations/overview").status_code == 405
    assert contents(store) == before

def test_stale_future_and_collection_error(settings, store, snapshot, monkeypatch):
    snapshot = snapshot.model_copy(update={"instrument": {"symbol": "BTCUSDT", "status": "Trading", "quote_coin": "USDT",
        "source_time_ms": snapshot.source_time_ms, "price_filter": {"tickSize": "0.1"},
        "lot_size_filter": {"basePrecision": "0.000001", "minOrderAmt": "5", "maxMarketOrderQty": "10"}}})
    store.save(snapshot)
    store.record_attempt(snapshot.source_time_ms, "BYBIT_UNAVAILABLE")
    before = contents(store)
    monkeypatch.setattr("cryptolab.paper.operations.time.time", lambda: snapshot.source_time_ms/1000)
    with TestClient(create_app(settings)) as client:
        fresh = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert next(m for m in fresh["markets"] if m["symbol"] == "BTCUSDT" and m["interval"] == "60")["status"] == "HEALTHY"
    monkeypatch.setattr("cryptolab.paper.operations.time.time", lambda: snapshot.source_time_ms/1000+91)
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        codes = {a["code"] for a in data["alerts"]}
        assert "PUBLIC_COLLECTION_FAILED" in codes and "MARKET_SNAPSHOT_STALE" in codes
        monkeypatch.setattr("cryptolab.paper.operations.time.time", lambda: snapshot.source_time_ms/1000-10)
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert "MARKET_TIMESTAMP_FUTURE" in {a["code"] for a in data["alerts"]}
    assert contents(store) == before

def test_paused_wallet_and_corruption_are_separate(settings, store):
    paper = PaperStore(store.path)
    w = paper.create_wallet(WalletSpec(bot_id="synthetic", strategy="trend", symbol="BTCUSDT", interval="60", initial_capital="1000", opened_at=0), "create")
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert any(a["code"] == "PAPER_WALLET_PAUSED" and a["severity"] == "INFO" for a in data["alerts"])
        with store.connect() as db: db.execute("UPDATE paper_heads SET event_hash=? WHERE wallet_id=?", ("0"*64, w["wallet_id"]))
        before = contents(store)
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert data["financial_integrity"] == "DEGRADED"
        assert any(a["code"] == "PAPER_LEDGER_INTEGRITY_FAILED" and a["severity"] == "CRITICAL" for a in data["alerts"])
        assert data["wallets"][0]["integrity"] == "FAILED"
        assert contents(store) == before

def test_tampered_dataset_reports_critical_and_does_not_touch_db(settings, store, snapshot):
    store.save(snapshot)
    with store.connect() as db:
        db.execute("UPDATE datasets SET payload='{}' WHERE id=?", (snapshot.dataset_id,))
    before = contents(store)
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        alert = next(a for a in data["alerts"] if a["code"] == "MARKET_INTEGRITY_FAILED")
        assert alert["severity"] == "CRITICAL" and alert["source_time_ms"] is None
    assert contents(store) == before

def test_monitor_checkpoint_without_signal_fails_closed(settings, store):
    from cryptolab.monitor.service import digest
    definition = {"config": {"bot_id": "synthetic"}}
    identifier, payload = digest(definition)
    with store.connect() as db:
        db.execute("INSERT INTO monitor_runtime(config_hash,bot_id,definition,last_candle,state) VALUES (?,?,?,?,?)",
                   (identifier, "synthetic", payload, 3600, "idle"))
    before = contents(store)
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert any(a["code"] == "MONITOR_INTEGRITY_FAILED" and a["severity"] == "CRITICAL" for a in data["alerts"])
    assert contents(store) == before

def test_missing_execution_evidence_is_critical(settings, store):
    paper = PaperStore(store.path)
    wallet = paper.create_wallet(WalletSpec(bot_id="orphan", strategy="trend", symbol="BTCUSDT", interval="60", initial_capital="1000", opened_at=0), "create")
    paper.append(wallet["wallet_id"], "activate", StateRecord(state="active", event_time=1))
    paper.append(wallet["wallet_id"], "exec-"+"a"*64, FillRecord(side="buy", quantity="1", price="100", fee="1", reference_price="100", candle_time=3600, event_time=3600))
    before = contents(store)
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert any(a["code"] == "PAPER_EVIDENCE_MISSING" and a["severity"] == "CRITICAL" for a in data["alerts"])
        assert data["wallets"][0]["integrity"] == "FAILED"
    assert contents(store) == before

def test_expired_decision_is_derived_without_checkpoint_write(services, monkeypatch):
    s, service = services
    binding = active(s, service); decision = record(s, service, binding)
    monkeypatch.setattr("cryptolab.paper.operations.time.time", lambda: decision["proposal"]["expires_at"]+1)
    before = contents(s[0])
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        data = client.get("/api/v1/paper/operations/overview").json()["data"]
        assert data["decisions"][0]["state"] == "RECORDED" and data["decisions"][0]["temporal_status"] == "EXPIRED"
        assert data["monitors"][0]["process_liveness"] == "UNKNOWN"
        assert any(a["code"] == "DECISION_EXPIRED" for a in data["alerts"])
    assert contents(s[0]) == before
