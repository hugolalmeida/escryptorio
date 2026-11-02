"""Cenários sintéticos e isolados; nenhuma chamada à corretora."""
import json
import os
import sqlite3
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.arena.models import ArenaConfig, ProtocolIds, STRATEGIES, StrategySet, StrategySpec
from cryptolab.arena.service import ArenaError, ArenaService, rank_entries
from cryptolab.engine.contracts import StrategyParameters
from cryptolab.history.storage import HistoryStore
from cryptolab.research.service import LEGACY_COMPATIBLE, ResearchService, digest
from test_backtest import research
from test_history import START, SyntheticSource, request_for, run_job


@pytest.fixture
def arena(research):
    research_service, spec = research
    config = ArenaConfig(dataset_hash=spec.dataset_hash, symbol="BTCUSDT", interval="60",
        train_start=START+60*3600, train_end=START+80*3600,
        validation_end=START+90*3600, test_end=START+100*3600)
    return ArenaService(research_service.store), config


def test_competition_equal_conditions_chronology_and_idempotence(arena, monkeypatch):
    service, config = arena
    calls = []
    original = service.research.run
    def traced(request):
        calls.append(request.partition)
        return original(request)
    monkeypatch.setattr(service.research, "run", traced)
    experiment = service.create(config)
    assert service.create(config) == experiment
    result = service.execute(experiment["id"])
    assert calls == ["train"]*4+["validation"]*4+["test"]*4
    assert service.result(experiment["id"]) == result
    assert service.execute(experiment["id"]) == result
    with service.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM arena_experiments").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM arena_results").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM research_protocols").fetchone()[0] == 4
        assert db.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0] == 12
    for partition, ranking in result["rankings"].items():
        entries = ranking["entries"]
        assert [D(e["net_return_pct"]) for e in entries] == sorted((D(e["net_return_pct"]) for e in entries), reverse=True)
        assert [e["rank"] for e in entries] == [1,2,2,2]  # fixture: close 102.01 vs open 100
        assert ranking["insufficient_sample"] and ranking["validated_winner"] is None
        assert ranking["out_of_sample"] == (partition == "test")
        for entry in entries:
            run = service.research.result(entry["run_id"])
            assert D(run["simulation"]["equity"][0]["cash"]) == config.backtest.capital
            assert D(run["simulation"]["equity"][0]["quantity"]) == 0
            assert run["manifest"]["config"] == config.backtest.model_dump(mode="json")
            assert run["manifest"]["dataset_hash"] == config.dataset_hash
            assert run["manifest"]["partition"] == partition
            assert entry["insufficient_sample"] and entry["closed_trades"] < 30


def test_ranking_uses_exact_decimal_and_competition_ties():
    from decimal import localcontext
    rows = [{"strategy":"b", "net_return_pct":"0.12345678901234567890123456789012"},
            {"strategy":"a", "net_return_pct":"0.12345678901234567890123456789013"},
            {"strategy":"c", "net_return_pct":"0.12345678901234567890123456789013"},
            {"strategy":"d", "net_return_pct":"-1"}]
    with localcontext() as ctx:
        ctx.prec = 6
        ranked = rank_entries(rows)
    assert [e["strategy"] for e in ranked] == ["a", "c", "b", "d"]
    assert [e["rank"] for e in ranked] == [1, 1, 3, 4]


def test_custom_strategy_parameters_freeze_independently(arena):
    service, config = arena
    custom = config.model_copy(update={"strategies": StrategySet(
        trend=StrategySpec(parameters=StrategyParameters(fast=3, slow=5, trend_entry="state")),
        rsi=StrategySpec(parameters=StrategyParameters(rsi_period=3)),
        breakout=StrategySpec(parameters=StrategyParameters(lookback=5)))})
    experiment = service.create(custom)
    result = service.execute(experiment["id"])
    for strategy in STRATEGIES:
        protocol = service.research.protocol(experiment["protocol_ids"][strategy])
        assert protocol["request"]["parameters"] == getattr(custom.strategies, strategy).parameters.model_dump(mode="json")
    assert result["rankings"]["test"]["out_of_sample"]


def test_incompatible_protocols_and_market_rejected(arena):
    service, config = arena
    experiment = service.create(config)
    protocol_ids = experiment["protocol_ids"]
    mixed = {**protocol_ids, "trend": protocol_ids["rsi"]}
    with pytest.raises(ArenaError, match="PROTOCOL_CONDITIONS_MISMATCH"):
        service.create(config.model_copy(update={"protocol_ids": ProtocolIds(**mixed)}))
    with pytest.raises(ArenaError, match="DATASET_MARKET_MISMATCH"):
        service.create(config.model_copy(update={"symbol": "ETHUSDT"}))
    incompatible = service.research.freeze(service._protocol_request(config, "trend").model_copy(update={
        "config": config.backtest.model_copy(update={"capital":D(999)})}))
    with pytest.raises(ArenaError, match="PROTOCOL_CONDITIONS_MISMATCH"):
        service.create(config.model_copy(update={"protocol_ids": ProtocolIds(**{**protocol_ids,"trend":incompatible["id"]})}))


def test_integrity_and_immutable_storage(arena):
    service, config = arena
    exp = service.create(config)
    result = service.execute(exp["id"])
    for table in ("arena_experiments", "arena_results"):
        with pytest.raises(sqlite3.IntegrityError):
            with service.store.connect() as db:
                db.execute(f"UPDATE {table} SET payload='{{}}'")
    with service.store.connect() as db:
        db.execute("DROP TRIGGER arena_results_no_update")
        db.execute("UPDATE arena_results SET payload='{}'")
    with pytest.raises(ArenaError, match="ARENA_RESULT_HASH_MISMATCH"):
        service.result(exp["id"])
    with service.store.connect() as db:
        db.execute("DROP TRIGGER arena_experiments_no_update")
        db.execute("UPDATE arena_experiments SET payload='{}'")
    with pytest.raises(ArenaError, match="ARENA_EXPERIMENT_HASH_MISMATCH"):
        service.experiment(exp["id"])
    assert result["id"]


def test_corrupted_referenced_run_is_not_ranked(arena):
    service, config = arena
    exp = service.create(config)
    service.execute(exp["id"])
    with service.store.connect() as db:
        db.execute("DROP TRIGGER research_runs_no_update")
        db.execute("UPDATE research_runs SET payload='{}' WHERE id=(SELECT id FROM research_runs LIMIT 1)")
    with pytest.raises(ValueError, match="RUN_HASH_MISMATCH"):
        service.result(exp["id"])


def test_legacy_protocols_keep_ids_and_work_when_audited(arena, monkeypatch):
    service, config = arena
    new = service.create(config)
    legacy = "85a5b51ab9a8a9a77e6e32f3ec887103b5dce701015077bf00b0335095d2168d"
    # Simulate the explicitly audited bridge on any test Python/runtime.
    from cryptolab.research.fingerprint import replay_fingerprint
    monkeypatch.setitem(LEGACY_COMPATIBLE, legacy, replay_fingerprint()["code_hash"])
    ids = {}
    for strategy in STRATEGIES:
        protocol = service.research.protocol(new["protocol_ids"][strategy])
        protocol.pop("fingerprint_scheme", None)
        protocol.pop("replay_dependencies", None)
        protocol["code_hash"] = legacy
        identifier, payload = digest(protocol)
        with service.store.connect() as db:
            db.execute("INSERT INTO research_protocols(id,payload) VALUES (?,?)", (identifier,payload))
        ids[strategy] = identifier
    cfg = config.model_copy(update={"protocol_ids": ProtocolIds(**ids)})
    legacy_exp = service.create(cfg)
    result = service.execute(legacy_exp["id"])
    assert legacy_exp["protocol_ids"] == ids
    assert all(service.research.verify(run)["identical"] for groups in result["run_ids"].values() for run in groups.values())
    with service.store.connect() as db:
        for identifier in ids.values():
            assert json.loads(db.execute("SELECT payload FROM research_protocols WHERE id=?",(identifier,)).fetchone()[0])["code_hash"] == legacy


def test_local_api_intent_host_and_no_real_orders(arena, settings, monkeypatch):
    service, config = arena
    monkeypatch.setenv("BYBIT_API_KEY", "synthetic-test-key-never-read")
    getenv = os.getenv
    def guarded_getenv(name, default=None):
        if name.startswith("BYBIT_"):
            raise AssertionError("Arena não deve consultar credenciais privadas")
        return getenv(name, default)
    monkeypatch.setattr(os, "getenv", guarded_getenv)
    headers = {"X-CryptoLab-Research":"1"}
    payload = config.model_dump(mode="json")
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/arena/experiments",json=payload).status_code == 403
        assert client.post("/api/v1/arena/experiments",json=payload,headers={**headers,"origin":"https://evil.invalid"}).status_code == 403
        assert client.post("/api/v1/arena/experiments",json=payload,headers={**headers,"host":"evil.invalid"}).status_code == 400
        assert client.post("/api/v1/arena/experiments",json={**payload,"symbol":"SOLUSDT"},headers=headers).status_code == 422
        exp = client.post("/api/v1/arena/experiments",json=payload,headers=headers).json()
        assert client.get("/api/v1/arena/experiments").json()["experiments"]
        assert client.get(f'/api/v1/arena/experiments/{exp["id"]}').json() == exp
        response = client.post("/api/v1/arena/execute",json={"experiment_id":exp["id"]},headers=headers)
        assert response.status_code == 200
        assert client.get(f'/api/v1/arena/experiments/{exp["id"]}/result').json() == response.json()
        assert "synthetic-test-key-never-read" not in response.text
        assert client.post("/api/v1/orders",json={},headers=headers).status_code == 404
        assert client.post("/api/v1/arena/orders",json={},headers=headers).status_code == 404


def test_arena_train_is_unchanged_when_future_candles_change(arena, tmp_path):
    service, config = arena
    first = service.execute(service.create(config)["id"])
    other = HistoryStore(tmp_path / "alternative.sqlite3")
    other.migrate()
    other.save(service.store.load("BTCUSDT", "60"))
    class AlternateSyntheticSource(SyntheticSource):
        def page(self, request):
            response = super().page(request)
            for row in response["result"]["list"]:
                if int(row[0])//1000 >= config.train_end:
                    row[1:5] = ["150", "155", "149", "154"]
            return response
    job, _ = run_job(other, request_for(100), AlternateSyntheticSource())
    changed = config.model_copy(update={"dataset_hash":job["dataset_id"]})
    second_service = ArenaService(other)
    second = second_service.execute(second_service.create(changed)["id"])
    for strategy in STRATEGIES:
        left = service.research.result(first["run_ids"]["train"][strategy])["simulation"]
        right = second_service.research.result(second["run_ids"]["train"][strategy])["simulation"]
        assert left == right
