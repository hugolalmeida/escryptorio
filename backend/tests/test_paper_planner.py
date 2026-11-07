"""Fixtures exclusivamente sintéticas, sem rede e sem execução pelo planejador."""
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D, localcontext

import pytest

from cryptolab.engine.contracts import StrategyParameters
from cryptolab.models import Candle
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.service import MonitorService, digest
from cryptolab.paper.models import FillRecord, MarkRecord, StateRecord, WalletSpec
from cryptolab.paper.planner import PlannerError, VirtualTradePlanner
from cryptolab.paper.planner_models import PlannerBinding
from cryptolab.paper.storage import PaperStore
from cryptolab.storage import canonical_dataset


@pytest.fixture
def setup_planner(store, snapshot):
    now = (snapshot.candles[-1].time+3600)*1000+10000
    last = snapshot.candles[-1]
    open_candle = last.model_copy(update={"time":last.time+3600, "closed":False})
    candles = list(snapshot.candles)+[open_candle]
    ticker = snapshot.ticker.model_copy(update={"source_time_ms":now, "price":last.close})
    instrument = {"symbol":"BTCUSDT", "status":"Trading", "quote_coin":"USDT", "source_time_ms":now,
        "price_filter":{"tickSize":"0.01"}, "lot_size_filter":{"basePrecision":"0.001", "minOrderQty":"0.001",
        "minOrderAmt":"5", "maxMarketOrderQty":"100", "maxMarketOrderAmt":"100000"}}
    fresh = snapshot.model_copy(update={"candles":candles,"dataset_id":canonical_dataset("BTCUSDT","60",candles)[0],
        "fetched_at_ms":now,"source_time_ms":now,"ticker":ticker,"instrument":instrument})
    store.save(fresh)
    config = MonitorConfig(bot_id="synthetic-bot", symbol="BTCUSDT", interval="60", strategy="trend",
                           parameters=StrategyParameters(fast=2,slow=3,trend_entry="state"))
    signal = MonitorRuntime(store, clock=lambda:now).once(config)
    paper = PaperStore(store.path)
    wallet = paper.create_wallet(WalletSpec(bot_id=config.bot_id,strategy=config.strategy,symbol=config.symbol,
                                interval=config.interval,initial_capital="1000",opened_at=0),"synthetic-create")
    paper.append(wallet["wallet_id"],"synthetic-activate",StateRecord(state="active",event_time=1))
    binding = {"wallet_id":wallet["wallet_id"],"wallet_hash":wallet["wallet_hash"],"monitor_config_hash":signal["config_hash"],
               "risk":{"risk_fraction":"0.01","exposure_fraction":"1","costs":{"fee_rate":"0.001","slippage_rate":"0.0005"}}}
    return store,paper,fresh,config,signal,wallet,binding,[now]


def plan(s):
    store,_,_,_,signal,wallet,binding,clock=s
    return VirtualTradePlanner(store.path,clock=lambda:clock[0]).plan(wallet["wallet_id"],signal["id"],binding)


def tables(store):
    with store.connect() as db:
        return {t:[tuple(r) for r in db.execute("SELECT * FROM "+t+" ORDER BY rowid")] for t in ("paper_wallets","paper_events","paper_heads")}


def test_buy_deterministic_readonly_and_decimal(setup_planner):
    s=setup_planner
    before=tables(s[0])
    result=plan(s)
    assert result["action"] == "BUY" and result["status"] == "CONDITIONAL_REVALIDATION_REQUIRED"
    assert result["execution_enabled"] is False and D(result["planned_quantity"]) > 0
    assert D(result["estimated_price"]) >= D(result["reference_price"])
    assert D(result["planned_risk"]) <= D("10")
    assert result["earliest_fill_candle"] == result["decision_candle"]+3600
    with localcontext() as ctx:
        ctx.prec=6
        assert plan(s) == result
    assert tables(s[0]) == before


def test_awaiting_next_open_and_no_retroactive_fill(setup_planner):
    s=setup_planner
    store,paper,snapshot,config,signal,wallet,binding,clock=s
    # The same closed dataset can be stored without its still-open candle.
    store.save(snapshot.model_copy(update={"candles":snapshot.candles[:-1]}))
    result=plan(s)
    assert result["status"] == "AWAITING_NEXT_OPEN" and result["planned_quantity"] is None
    assert result["execution_enabled"] is False


def test_wallet_paused_and_binding_mismatch(setup_planner):
    s=setup_planner
    s[1].append(s[5]["wallet_id"],"pause",StateRecord(state="paused",event_time=2))
    with pytest.raises(PlannerError,match="WALLET_PAUSED"): plan(s)
    s[6]["wallet_hash"]="0"*64
    with pytest.raises(PlannerError,match="BINDING_WALLET_MISMATCH"): plan(s)


def test_expired_stale_and_changed_ledger(setup_planner):
    s=setup_planner
    first=plan(s)
    s[1].append(s[5]["wallet_id"],"new-mark",MarkRecord(price=str(s[2].ticker.price),candle_time=s[3] and s[4]["decision_time"],event_time=s[7][0]//1000))
    second=plan(s)
    assert first["wallet_sequence"]+1 == second["wallet_sequence"] and first["validation_hash"] != second["validation_hash"]
    s[7][0] += 91000
    with pytest.raises(PlannerError,match="STALE_SNAPSHOT"): plan(s)
    s[7][0] = s[4]["valid_until"]*1000
    with pytest.raises(PlannerError,match="SIGNAL_EXPIRED"): plan(s)


def test_schema_legacy_and_historical_rejected(setup_planner):
    s=setup_planner
    store,_,_,config,_,wallet,binding,clock=s
    legacy=MonitorService(store).evaluate(config,clock[0])
    binding["monitor_config_hash"]=legacy["config_hash"]
    with pytest.raises(PlannerError,match="UNSUPPORTED_SIGNAL_SCHEMA"):
        VirtualTradePlanner(store.path,clock=lambda:clock[0]).plan(wallet["wallet_id"],legacy["id"],binding)
    binding["monitor_config_hash"]=s[4]["config_hash"]
    signal=dict(s[4]); signal.pop("id"); signal["origin"]="historical_recovered"; signal["eligible_for_future_paper_analysis"]=False
    identifier,payload=digest(signal)
    with store.connect() as db:
        db.execute("DROP TRIGGER monitor_signals_no_delete")
        db.execute("DELETE FROM monitor_signals WHERE id=?",(s[4]["id"],))
        db.execute("INSERT INTO monitor_signals VALUES (?,?,?,?,?)",(identifier,config.bot_id,signal["config_hash"],signal["candle_time"],payload))
    with pytest.raises(PlannerError,match="SIGNAL_NOT_ELIGIBLE"):
        VirtualTradePlanner(store.path,clock=lambda:clock[0]).plan(wallet["wallet_id"],identifier,binding)


def test_tampered_signal_and_dataset(setup_planner):
    s=setup_planner
    with s[0].connect() as db:
        db.execute("DROP TRIGGER monitor_signals_no_update")
        db.execute("UPDATE monitor_signals SET payload='{}' WHERE id=?",(s[4]["id"],))
    with pytest.raises(PlannerError,match="SIGNAL_INTEGRITY_ERROR"): plan(s)


def test_tampered_market_dataset_rejected(setup_planner):
    s=setup_planner
    with s[0].connect() as db:
        db.execute("UPDATE datasets SET payload='{}' WHERE id=?",(s[4]["dataset_id"],))
    with pytest.raises(PlannerError,match="SIGNAL_DATASET_MISMATCH"): plan(s)


def test_missing_public_limit_fails_closed(setup_planner):
    s=setup_planner
    raw=dict(s[2].instrument); lots=dict(raw["lot_size_filter"]); lots.pop("minOrderAmt"); raw["lot_size_filter"]=lots
    s[0].save(s[2].model_copy(update={"instrument":raw}))
    with pytest.raises(PlannerError,match="INSTRUMENT_LIMITS_INCOMPLETE"): plan(s)


def test_insufficient_balance_fails_without_ledger_writes(setup_planner):
    s=setup_planner
    wid=s[5]["wallet_id"]
    s[1].append(wid,"fixture-buy",FillRecord(side="buy",quantity="10",price="100",fee="0",reference_price="100",candle_time=3600,event_time=3600))
    s[1].append(wid,"fixture-sell",FillRecord(side="sell",quantity="10",price="0.1",fee="0",reference_price="100",candle_time=3600,event_time=3600))
    before=tables(s[0])
    with pytest.raises(PlannerError,match="INSUFFICIENT_BALANCE_OR_INSTRUMENT_MINIMUM"): plan(s)
    assert tables(s[0]) == before


def test_ledger_integrity_error_is_rejected(setup_planner):
    s=setup_planner
    with s[0].connect() as db:
        db.execute("DROP TRIGGER paper_events_no_update")
        db.execute("UPDATE paper_events SET payload='{}' WHERE sequence=1")
    with pytest.raises(PlannerError,match="LEDGER_INTEGRITY_ERROR"): plan(s)


def test_concurrent_read_only_plans(setup_planner):
    before=tables(setup_planner[0])
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _:plan(setup_planner), range(6)))
    assert len({x["validation_hash"] for x in results}) == 1
    assert tables(setup_planner[0]) == before


def test_instrument_minimum_and_float_rejection(setup_planner):
    s=setup_planner
    snap=s[2]
    raw=dict(snap.instrument); lots=dict(raw["lot_size_filter"]); lots["minOrderAmt"]="99999"; raw["lot_size_filter"]=lots
    s[0].save(snap.model_copy(update={"instrument":raw}))
    with pytest.raises(PlannerError,match="INSUFFICIENT_BALANCE_OR_INSTRUMENT_MINIMUM"): plan(s)
    s[6]["risk"]["costs"]["fee_rate"]=0.1
    with pytest.raises(ValueError,match="strings ou Decimal"): PlannerBinding.model_validate(s[6])


def test_sell_above_position_prohibited():
    with pytest.raises(PlannerError,match="SELL_EXCEEDS_POSITION"):
        VirtualTradePlanner.validate_sell_quantity(D("2"), D("1"))


def test_ambiguous_bot_config_rejected(setup_planner):
    s=setup_planner
    config=s[3].model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    MonitorRuntime(s[0],clock=lambda:s[7][0]).once(config)
    with pytest.raises(PlannerError,match="AMBIGUOUS_BOT_CONFIG"): plan(s)


def test_wallet_or_config_mismatch(setup_planner):
    s=setup_planner
    s[6]["monitor_config_hash"]="0"*64
    with pytest.raises(PlannerError,match="BINDING_CONFIG_MISMATCH"): plan(s)
    s[6]["monitor_config_hash"]=s[4]["config_hash"]
    other=s[1].create_wallet(WalletSpec(bot_id="other-bot",strategy="trend",symbol="BTCUSDT",interval="60",initial_capital="1000",opened_at=0),"other-create")
    s[6]["wallet_id"]=other["wallet_id"]; s[6]["wallet_hash"]=other["wallet_hash"]
    with pytest.raises(PlannerError,match="WALLET_CONFIG_MISMATCH"):
        VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(other["wallet_id"],s[4]["id"],s[6])


def test_version_or_financial_fingerprint_incompatible(setup_planner, monkeypatch):
    s=setup_planner
    monkeypatch.setattr("cryptolab.monitor.runtime.monitor_fingerprint",lambda:"0"*64)
    with pytest.raises(PlannerError,match="MONITOR_VERSION_INCOMPATIBLE"): plan(s)


def test_concurrent_ledger_change_requires_retry(setup_planner, monkeypatch):
    s=setup_planner
    planner=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0])
    original=planner._read
    calls=[0]
    def read(*args):
        result=original(*args)
        calls[0]+=1
        if calls[0]==1:
            s[1].append(s[5]["wallet_id"],"concurrent-mark",MarkRecord(price=str(s[2].ticker.price),candle_time=s[4]["decision_time"],event_time=s[7][0]//1000))
        return result
    monkeypatch.setattr(planner,"_read",read)
    with pytest.raises(PlannerError,match="STATE_CHANGED_RETRY"):
        planner.plan(s[5]["wallet_id"],s[4]["id"],s[6])


def test_readonly_cli_status_and_live_guard(setup_planner, tmp_path, monkeypatch, capsys):
    from cryptolab.paper.planner_cli import main
    s=setup_planner
    binding=tmp_path/"binding.json"
    binding.write_text(json.dumps(s[6]),encoding="utf-8")
    monkeypatch.setenv("CRYPTOLAB_DATABASE",str(s[0].path))
    monkeypatch.setattr("cryptolab.paper.planner.time.time",lambda:s[7][0]/1000)
    monkeypatch.setattr("sys.argv",["planner","--wallet",s[5]["wallet_id"],"--signal",s[4]["id"],"--binding",str(binding)])
    before=tables(s[0])
    assert main()==0 and json.loads(capsys.readouterr().out)["execution_enabled"] is False
    assert tables(s[0])==before
    s[1].append(s[5]["wallet_id"],"cli-pause",StateRecord(state="paused",event_time=2))
    assert main()==1
    blocked=json.loads(capsys.readouterr().out)
    assert blocked["error"] == "WALLET_PAUSED" and blocked["signal_id"] == s[4]["id"] and blocked["binding_hash"]
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError): main()


@pytest.mark.parametrize("strategy,expected", [("trend","SELL"), ("buy_hold","HOLD")])
def test_position_selects_long_decision(setup_planner, strategy, expected):
    store,paper,snapshot,_,_,_,_,clock=setup_planner
    candles=list(snapshot.candles)
    if strategy == "trend":
        for index, price in ((-4,"190"),(-3,"170"),(-2,"150")):
            old=candles[index]
            p=D(price)
            candles[index]=Candle(time=old.time,open=p,high=p+1,low=p-1,close=p,volume=old.volume,turnover=old.turnover,closed=True)
    ticker=snapshot.ticker.model_copy(update={"price":candles[-2].close})
    changed=snapshot.model_copy(update={"candles":candles,"ticker":ticker,"dataset_id":canonical_dataset("BTCUSDT","60",candles)[0]})
    store.save(changed)
    config=MonitorConfig(bot_id="position-"+strategy,symbol="BTCUSDT",interval="60",strategy=strategy,
        parameters=StrategyParameters(fast=2,slow=3,trend_entry="state"))
    signal=MonitorRuntime(store,clock=lambda:clock[0]).once(config)
    wallet=paper.create_wallet(WalletSpec(bot_id=config.bot_id,strategy=strategy,symbol="BTCUSDT",interval="60",initial_capital="1000",opened_at=0),"create-"+strategy)
    wid=wallet["wallet_id"]
    paper.append(wid,"activate",StateRecord(state="active",event_time=1))
    paper.append(wid,"synthetic-fill",FillRecord(side="buy",quantity="1",price="100",fee="0",reference_price="100",candle_time=3600,event_time=3600))
    paper.append(wid,"mark",MarkRecord(price=ticker.price,candle_time=signal["decision_time"],event_time=clock[0]//1000))
    binding={"wallet_id":wid,"wallet_hash":wallet["wallet_hash"],"monitor_config_hash":signal["config_hash"],
             "risk":{"risk_fraction":"0.01","exposure_fraction":"1","costs":{"fee_rate":"0.001","slippage_rate":"0.0005"}}}
    before=tables(store)
    result=VirtualTradePlanner(store.path,clock=lambda:clock[0]).plan(wid,signal["id"],binding)
    assert result["action"] == expected and result["status"] == ("HOLD" if expected == "HOLD" else "CONDITIONAL_REVALIDATION_REQUIRED")
    if expected == "SELL": assert D(result["planned_quantity"]) <= D(1)
    assert tables(store) == before
