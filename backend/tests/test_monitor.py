"""Snapshots sintéticos de teste; a aplicação não fornece dados fictícios."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D, ROUND_UP, localcontext

import pytest

from cryptolab.engine.contracts import StrategyParameters
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.service import MonitorError, MonitorService
from cryptolab.monitor.__main__ import main
from cryptolab.paper.models import WalletSpec
from cryptolab.paper.storage import PaperStore
from cryptolab.storage import Store, canonical_dataset


@pytest.fixture
def monitor(store, snapshot):
    stamp = (snapshot.candles[-1].time+3600)*1000+10000
    fresh = snapshot.model_copy(update={"fetched_at_ms":stamp, "source_time_ms":stamp})
    store.save(fresh)
    config = MonitorConfig(bot_id="bot-test",symbol="BTCUSDT",interval="60",strategy="trend",
        parameters=StrategyParameters(fast=2,slow=3,trend_entry="state"))
    return MonitorService(store),fresh,config,stamp


def save_snapshot(store, source, candles, stamp):
    dataset = canonical_dataset(source.symbol,source.interval,candles)[0]
    changed = source.model_copy(update={"candles":candles,"dataset_id":dataset,
        "fetched_at_ms":stamp,"source_time_ms":stamp})
    store.save(changed)
    return changed


@pytest.mark.parametrize("strategy",["trend","rsi","breakout","buy_hold"])
def test_closed_causal_decisions_and_stable_ids(monitor,strategy):
    service,snapshot,config,now = monitor
    config = config.model_copy(update={"strategy":strategy})
    result = service.evaluate(config,now)
    assert result["candle_time"] == snapshot.candles[-1].time
    assert result["decision_time"] == result["candle_time"]+3600
    assert result["mode"] == "informational_only" and result["position_checked"] is False
    assert result["if_flat"]["action"] in ("buy","hold")
    assert result["if_long"]["action"] in ("sell","hold")
    assert service.evaluate(config,now+20000) == result
    assert service.signals(config.bot_id)[0] == result


@pytest.mark.parametrize("strategy",["trend","rsi","breakout","buy_hold"])
def test_prefix_causality_and_ignore_open_candle(monitor,strategy):
    service,snapshot,config,now = monitor
    config=config.model_copy(update={"strategy":strategy})
    baseline=service.evaluate(config,now)
    last=snapshot.candles[-1]
    open_candle=last.model_copy(update={"time":last.time+3600,"closed":False,"open":D(999),"high":D(999),"low":D(999),"close":D(999)})
    save_snapshot(service.store,snapshot,list(snapshot.candles)+[open_candle],now)
    assert service.evaluate(config,now) == baseline
    changed=open_candle.model_copy(update={"open":D(500),"high":D(500),"low":D(500),"close":D(500)})
    save_snapshot(service.store,snapshot,list(snapshot.candles)+[changed],now)
    assert service.evaluate(config,now) == baseline


@pytest.mark.parametrize("problem",["stale","future_clock","missing","duplicate","unclosed","future_candle","hash","warmup","boundary"])
def test_refuse_invalid_snapshots(monitor,problem):
    service,snapshot,config,now = monitor
    candles=list(snapshot.candles)
    stamp=now
    if problem == "stale": now += 91000
    elif problem == "future_clock": now -= 6000
    elif problem == "missing": candles.pop(30)
    elif problem == "duplicate": candles[30]=candles[29]
    elif problem == "unclosed": candles[-1]=candles[-1].model_copy(update={"closed":False})
    elif problem == "future_candle": candles.append(candles[-1].model_copy(update={"time":candles[-1].time+7200,"closed":False}))
    elif problem == "warmup": config=config.model_copy(update={"parameters":StrategyParameters(slow=100)})
    elif problem == "boundary": now += 3600000
    if problem in ("missing","duplicate","unclosed","future_candle"):
        save_snapshot(service.store,snapshot,candles,stamp)
    elif problem == "hash":
        with service.store.connect() as db:
            db.execute("UPDATE snapshots SET payload=? WHERE symbol=? AND interval=?",(snapshot.model_copy(update={"dataset_id":"0"*64}).model_dump_json(),"BTCUSDT","60"))
    with pytest.raises(MonitorError): service.evaluate(config,now)
    assert not service.signals()


def test_conflicting_data_and_immutable_signal(monitor):
    service,snapshot,config,now = monitor
    signal=service.evaluate(config,now)
    changed=list(snapshot.candles)
    changed[-1]=changed[-1].model_copy(update={"close":changed[-1].close+D("0.1")})
    save_snapshot(service.store,snapshot,changed,now)
    with pytest.raises(MonitorError,match="SIGNAL_CONFLICT"): service.evaluate(config,now)
    with pytest.raises(sqlite3.IntegrityError):
        with service.store.connect() as db: db.execute("UPDATE monitor_signals SET payload='{}'")
    with service.store.connect() as db:
        db.execute("DROP TRIGGER monitor_signals_no_update")
        db.execute("UPDATE monitor_signals SET payload='{}'")
    with pytest.raises(MonitorError,match="SIGNAL_INTEGRITY_ERROR"): service.signals()
    assert signal["id"]


def test_tampered_snapshot_dataset_rejected(monitor):
    service,snapshot,config,now=monitor
    with service.store.connect() as db:
        db.execute("UPDATE datasets SET payload='{}' WHERE id=?",(snapshot.dataset_id,))
    with pytest.raises(MonitorError,match="DATASET_INTEGRITY"):
        service.evaluate(config,now)
    assert service.signals() == []


def test_concurrent_once_and_ledger_unchanged(monitor):
    service,snapshot,config,now = monitor
    paper=PaperStore(service.store.path)
    wallet=paper.create_wallet(WalletSpec(bot_id="bot-test",strategy="trend",symbol="BTCUSDT",interval="60",initial_capital="1000",opened_at=0),"create-test")
    before=paper.events(wallet["wallet_id"])
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids=list(pool.map(lambda _: MonitorService(Store(service.store.path)).evaluate(config,now)["id"],range(6)))
    assert len(set(ids)) == 1 and len(service.signals()) == 1
    assert paper.events(wallet["wallet_id"]) == before
    assert paper.wallet(wallet["wallet_id"]) == wallet


def test_idempotency_is_scoped_to_bot_and_configuration(monitor):
    service,snapshot,config,now=monitor
    original=service.evaluate(config,now)
    changed=config.model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    other=service.evaluate(changed,now)
    second_bot=service.evaluate(config.model_copy(update={"bot_id":"other-bot"}),now)
    assert len({original["id"],other["id"],second_bot["id"]}) == 3
    assert len(service.signals()) == 3


def test_restart_gap_fails_closed_and_sequential_recovery(monitor):
    service,snapshot,config,now=monitor
    first=service.evaluate(config,now)
    def advance(count):
        last=snapshot.candles[-1]
        extension=[last.model_copy(update={"time":last.time+i*3600}) for i in range(1,count+1)]
        return save_snapshot(service.store,snapshot,list(snapshot.candles)+extension,now+count*3600000)
    advance(2)
    restarted=MonitorService(Store(service.store.path))
    with pytest.raises(MonitorError,match="MISSED_OR_REWOUND_CANDLES"): restarted.evaluate(config,now+7200000)
    advance(1)
    second=restarted.evaluate(config,now+3600000)
    assert second["candle_time"] == first["candle_time"]+3600
    advance(2)
    assert restarted.evaluate(config,now+7200000)["candle_time"] == first["candle_time"]+7200


def test_rounding_and_changed_engine_blocked(monitor,monkeypatch):
    service,snapshot,config,now=monitor
    signal=service.evaluate(config,now)
    with localcontext() as ctx:
        ctx.prec=6; ctx.rounding=ROUND_UP
        assert service.evaluate(config,now) == signal
    monkeypatch.setattr("cryptolab.monitor.service.STARTUP_ENGINE_HASH","0"*64)
    with pytest.raises(MonitorError,match="ENGINE_CHANGED"): service.evaluate(config,now)


def test_boundary_crossing_during_evaluation_fails_closed(monitor,monkeypatch):
    service,snapshot,config,now=monitor
    times=iter([now/1000,(now+3600000)/1000])
    monkeypatch.setattr("cryptolab.monitor.service.time.time",lambda:next(times))
    with pytest.raises(MonitorError,match="STALE"):
        service.evaluate(config)
    assert service.signals() == []


def test_snapshot_replacement_during_evaluation_fails_closed(monitor,monkeypatch):
    import cryptolab.monitor.service as module
    service,snapshot,config,now=monitor
    original=module.replay_fingerprint
    def replace():
        candles=list(snapshot.candles)
        candles[-1]=candles[-1].model_copy(update={"close":candles[-1].close+D("0.1")})
        save_snapshot(service.store,snapshot,candles,now)
        return original()
    monkeypatch.setattr(module,"replay_fingerprint",replace)
    with pytest.raises(MonitorError,match="SNAPSHOT_CHANGED"):
        service.evaluate(config,now)
    assert service.signals() == []


def test_cli_once_diagnostics_and_live_guard(monitor,settings,tmp_path,monkeypatch,capsys):
    service,snapshot,config,now=monitor
    path=tmp_path/"monitor.json"
    path.write_text(config.model_dump_json(),encoding="utf-8")
    monkeypatch.setenv("CRYPTOLAB_DATABASE",str(settings.database_path))
    monkeypatch.setattr("cryptolab.monitor.service.time.time",lambda:now/1000)
    monkeypatch.setattr("sys.argv",["monitor","--once","--config",str(path)])
    assert main() == 0
    item=json.loads(capsys.readouterr().out)
    monkeypatch.setattr("sys.argv",["monitor","--signals","--bot",config.bot_id])
    assert main() == 0 and json.loads(capsys.readouterr().out)[0]["id"] == item["id"]
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError): main()
