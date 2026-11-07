"""Fixtures sintéticas isoladas; nenhuma conexão de rede ou execução de trades."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from cryptolab.history.models import HistoryRequest, canonical_history, utc_iso, canonical_json
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.runtime import LEASE_MS, MonitorRuntime
from cryptolab.monitor.service import MonitorError, MonitorService
from cryptolab.storage import Store, canonical_dataset


@pytest.fixture
def scenario(store, snapshot):
    now = (snapshot.candles[-1].time+3600)*1000+10000
    fresh = snapshot.model_copy(update={"fetched_at_ms": now, "source_time_ms": now})
    store.save(fresh)
    config = MonitorConfig(bot_id="runtime-test", symbol="BTCUSDT", interval="60", strategy="buy_hold")
    clock = [now]
    return store, fresh, config, clock


def advance(store, snapshot, clock, count):
    last = snapshot.candles[-1]
    candles = list(snapshot.candles) + [last.model_copy(update={"time": last.time+i*3600}) for i in range(1, count+1)]
    clock[0] += count*3600000
    store.save(snapshot.model_copy(update={"candles": candles, "dataset_id": canonical_dataset("BTCUSDT", "60", candles)[0],
                                           "fetched_at_ms": clock[0], "source_time_ms": clock[0]}))
    return candles


def approved(store, candles):
    req = HistoryRequest(symbol="BTCUSDT", interval="60", start=utc_iso(candles[0].time), end=utc_iso(candles[-1].time+3600))
    identifier, payload = canonical_history(req, candles)
    manifest = {"dataset_id": identifier, "sha256": identifier, "schema_version": 1, "source": "Bybit", "market": "spot",
                "symbol": "BTCUSDT", "interval": "60", "start_time": req.start_time, "end_time": req.end_time,
                "candle_count": len(candles), "coverage_ratio": 1, "gaps": [], "integrity_status": "approved"}
    with store.connect() as db:
        db.execute("INSERT INTO historical_datasets VALUES (?,?,?,?,?,?,?,?,?)", (identifier,"BTCUSDT","60",req.start_time,req.end_time,len(candles),1,canonical_json(manifest),payload))
    return identifier


def test_restart_stale_and_gap_fail_closed(scenario):
    store, snapshot, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    first = runtime.once(config)
    assert MonitorRuntime(Store(store.path), clock=lambda: clock[0]).once(config) == first
    advance(store, snapshot, clock, 2)
    with pytest.raises(MonitorError, match="RECOVERY_DATASET_REQUIRED"):
        runtime.once(config)
    status = runtime.status()[0]
    assert status["last_candle"] == first["candle_time"] and status["error_code"] == "RECOVERY_DATASET_REQUIRED"
    clock[0] += 91000
    with pytest.raises(MonitorError, match="STALE_SNAPSHOT"):
        runtime.once(config)
    assert len(runtime.catalog.signals()) == 1


@pytest.mark.parametrize("strategy", ["trend", "rsi", "breakout", "buy_hold"])
def test_recovery_is_causal_and_never_eligible(scenario, strategy):
    store, snapshot, config, clock = scenario
    config = config.model_copy(update={"strategy": strategy})
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    first = runtime.once(config)
    candles = advance(store, snapshot, clock, 3)
    dataset = approved(store, candles[:-1])
    current = runtime.once(config, dataset)
    items = runtime.catalog.signals(config.bot_id)
    recovered = sorted((s for s in items if s.get("origin") == "historical_recovered"), key=lambda s: s["candle_time"])
    assert [s["candle_time"] for s in recovered] == [first["candle_time"]+3600, first["candle_time"]+7200]
    assert all(not s["eligible_for_future_paper_analysis"] and s["dataset_id"] == dataset for s in recovered)
    assert current["origin"] == "current" and current["eligible_for_future_paper_analysis"]
    definition = runtime.definition(config)
    for s in recovered:
        prefix = tuple(c for c in candles if c.time <= s["candle_time"])
        expected = runtime._signal(config, definition, s["config_hash"], prefix, dataset, "historical_recovered")
        assert s["if_flat"] == expected["if_flat"] and s["if_long"] == expected["if_long"]
    assert runtime.once(config, dataset) == current
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM paper_events").fetchone()[0] == 0


def test_lease_exclusion_expiry_fencing_and_restart(scenario):
    store, _, config, clock = scenario
    a = MonitorRuntime(store, clock=lambda: clock[0])
    b = MonitorRuntime(Store(store.path), clock=lambda: clock[0])
    key, owner, _ = a.claim(config)
    with pytest.raises(MonitorError, match="MONITOR_LEASE_BUSY"):
        b.claim(config)
    clock[0] += LEASE_MS+1
    newkey, newowner, _ = b.claim(config)
    assert newkey == key and newowner != owner
    with store.connect() as db:
        with pytest.raises(MonitorError, match="MONITOR_LEASE_LOST"):
            a._owned(db, key, owner)
    a.release(key, owner, "MONITOR_INTERRUPTED")
    assert b.status()[0]["lease_active"]
    b.release(key, newowner)
    assert not b.status()[0]["lease_active"]


def test_simultaneous_instances_only_one_claim(scenario):
    store, _, config, clock = scenario
    def claim(_):
        try:
            return MonitorRuntime(Store(store.path), clock=lambda: clock[0]).claim(config)[1]
        except MonitorError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(claim, range(6)))
    assert outcomes.count("MONITOR_LEASE_BUSY") == 5


def test_interrupt_releases_lease_and_loop_stops(scenario, monkeypatch):
    store, _, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    monkeypatch.setattr(runtime, "_signal", lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    runtime.loop(config, sleeper=lambda _: None, emit=lambda _: None)
    status = runtime.status()[0]
    assert not status["lease_active"] and status["error_code"] == "MONITOR_INTERRUPTED"
    with pytest.raises(ValueError): runtime.loop(config, poll_seconds=1)


def test_integrity_of_existing_legacy_signal_and_version_transition(scenario):
    store, _, config, clock = scenario
    legacy = MonitorService(store).evaluate(config, clock[0])
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    current = runtime.once(config)
    assert legacy in runtime.catalog.signals() and current["definition"]["monitor_hash"]
    assert runtime.status()[0]["last_candle"] == legacy["candle_time"]
    with store.connect() as db:
        db.execute("DROP TRIGGER monitor_signals_no_update")
        db.execute("UPDATE monitor_signals SET payload='{}' WHERE id=?", (legacy["id"],))
    with pytest.raises(MonitorError, match="SIGNAL_INTEGRITY_ERROR"):
        runtime.catalog.signals()


def test_recovery_rejects_tampered_history_and_preserves_checkpoint(scenario):
    store, snapshot, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    first = runtime.once(config)
    candles = advance(store, snapshot, clock, 3)
    dataset = approved(store, candles[:-1])
    with store.connect() as db:
        db.execute("DROP TRIGGER historical_datasets_no_update")
        db.execute("UPDATE historical_datasets SET payload='{}' WHERE id=?", (dataset,))
    with pytest.raises(MonitorError, match="DATASET_HASH_MISMATCH"):
        runtime.once(config, dataset)
    assert runtime.status()[0]["last_candle"] == first["candle_time"]
    assert len(runtime.catalog.signals()) == 1


def test_recovery_rejects_conflicting_overlap(scenario):
    store, snapshot, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    runtime.once(config)
    candles = advance(store, snapshot, clock, 3)
    altered = list(candles[:-1])
    altered[-1] = altered[-1].model_copy(update={"close": altered[-1].close - 1})
    dataset = approved(store, altered)
    with pytest.raises(MonitorError, match="RECOVERY_CANDLE_CONFLICT"):
        runtime.once(config, dataset)
    assert len(runtime.catalog.signals()) == 1


def test_runtime_checkpoint_tampering_is_rejected(scenario):
    store, _, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    runtime.once(config)
    with store.connect() as db:
        db.execute("UPDATE monitor_runtime SET last_candle=last_candle+3600")
    with pytest.raises(MonitorError, match="MONITOR_CHECKPOINT_INTEGRITY_ERROR"):
        runtime.once(config)


def test_monitor_code_change_requires_restart(scenario, monkeypatch):
    store, _, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    runtime.once(config)
    monkeypatch.setattr("cryptolab.monitor.runtime.monitor_fingerprint", lambda: "f" * 64)
    with pytest.raises(MonitorError, match="MONITOR_CHANGED_RESTART_REQUIRED"):
        runtime.once(config)
    assert len(runtime.catalog.signals()) == 1


def test_loop_interrupt_during_wait(scenario):
    store, _, config, clock = scenario
    runtime = MonitorRuntime(store, clock=lambda: clock[0])
    messages = []
    def interrupt(_):
        raise KeyboardInterrupt
    runtime.loop(config, sleeper=interrupt, emit=messages.append)
    assert len(messages) == 1 and json.loads(messages[0])["origin"] == "current"
    assert not runtime.status()[0]["lease_active"]


def test_cli_status(scenario, monkeypatch, capsys):
    from cryptolab.monitor.__main__ import main
    store, _, config, clock = scenario
    MonitorRuntime(store, clock=lambda: clock[0]).once(config)
    monkeypatch.setenv("CRYPTOLAB_DATABASE", str(store.path))
    monkeypatch.setattr("sys.argv", ["monitor", "--status", "--bot", config.bot_id])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)[0]["bot_id"] == config.bot_id
