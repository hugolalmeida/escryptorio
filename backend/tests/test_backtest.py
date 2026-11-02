"""Synthetic mathematical fixtures only; never exposed by application endpoints."""
import sqlite3
from decimal import Decimal as D, localcontext

import pytest
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.engine.backtest import simulate, metrics
from cryptolab.engine.contracts import (BacktestConfig, CostModel, InstrumentRules, StrategyParameters,
    EquityPoint, Fill, Trade)
from cryptolab.engine.strategies import ResearchStrategy, warmup
from cryptolab.history.storage import HistoryStore, HistoryError
from cryptolab.models import Candle
from cryptolab.research.service import ProtocolRequest, ResearchService, RunRequest, ResearchError
from test_history import run_job, request_for, START

RULES = InstrumentRules(symbol="BTCUSDT", quantity_step="0.001", price_tick="0.01", min_quantity="0.001",
    min_notional="1", max_quantity="100000", max_notional="10000000", source_time_ms=0, source_hash="synthetic-test")
PARAMS = StrategyParameters(fast=2, slow=3, lookback=2, rsi_period=2, stop_fraction="0.1", target_fraction="0.2", trend_entry="state")
CONFIG = BacktestConfig(capital="1000", risk_fraction="1", costs=CostModel(fee_rate=0, slippage_rate=0))


def series(prices):
    return tuple(Candle(time=i*3600, open=D(str(p)), close=D(str(p)), high=D(str(p)), low=D(str(p)),
                        volume=D(10), turnover=D(1000), closed=True) for i, p in enumerate(prices))


def replay(candles, strategy="buy_hold", start=0, config=CONFIG, parameters=PARAMS, rules=RULES):
    return simulate(candles, 3600, start*3600, len(candles)*3600, strategy, parameters, config, rules)


def test_buy_hold_next_open_costs_and_cash_reference():
    cfg = CONFIG.model_copy(update={"costs": CostModel(fee_rate="0.01", slippage_rate="0.01")})
    result = replay(series([90, 100, 110]), config=cfg)
    buy, sell = result.fills
    # Independently: floor(1000/(101*1.01), .001)=9.802; exit=110*.99=108.90.
    assert buy.candle_time == 3600 and buy.price == D(101) and buy.quantity == D("9.802")
    assert buy.fee == D("9.90002") and buy.cash_after == D("0.09798")
    assert sell.price == D("108.90") and sell.fee == D("10.674378")
    assert result.metrics.pnl == D("56.861402")
    assert result.metrics.fees == D("20.574398")
    assert result.metrics.slippage_cost == D("20.5842")
    assert result.trades[0].pnl == result.metrics.pnl
    assert result.metrics.profit_factor is None and "profit_factor" in result.metrics.undefined


@pytest.mark.parametrize("low,high,expected,reason", [(90,130,"92.7","stop_intrabar"), (100,130,"123.60","target_intrabar")])
def test_stop_and_target_same_candle_conservative(low, high, expected, reason):
    candles = list(series([100,101,102,103,103,103]))
    candles[4] = Candle(time=14400, open=103, high=high, low=low, close=103, volume=10, turnover=1000, closed=True)
    result = replay(tuple(candles), "trend", start=3)
    assert result.fills[0].candle_time == 14400
    assert result.fills[1].reason == reason
    assert result.fills[1].price == D(expected)


@pytest.mark.parametrize("gap,expected,reason", [(80,"80","stop_gap"), (130,"130","target_gap")])
def test_gap_uses_open_not_unreachable_stop(gap, expected, reason):
    result = replay(series([100,101,102,103,104,gap]), "trend", start=3)
    assert result.fills[1].reason == reason and result.fills[1].price == D(expected)
    assert result.trades[0].planned_stop == D("93.6")


def test_open_position_mtm_drawdown_and_undefined():
    result = replay(series([100,100,80]), config=CONFIG.model_copy(update={"final_policy": "mark_to_market"}))
    assert result.portfolio.position.quantity == 10
    assert result.metrics.max_drawdown_pct == 20
    assert result.metrics.pnl == -200
    assert result.metrics.closed_trades == 0 and result.metrics.win_rate_pct is None
    assert result.metrics.exposure_pct == D("66.66666666666666666666666666666667")


def test_no_trades_no_fake_metrics_and_warmup():
    result = replay(series([100]*10), "trend", start=3)
    assert result.metrics.pnl == 0 and result.metrics.profit_factor is None
    assert result.metrics.expectancy is None and result.metrics.exposure_pct == 0
    with pytest.raises(ValueError, match="Warm-up"):
        replay(series([100]*10), "trend")


@pytest.mark.parametrize("strategy", ["trend", "rsi", "breakout", "buy_hold"])
def test_strategy_prefix_invariance(strategy):
    candles = series([100+(i%13)*2-(i%7) for i in range(80)])
    full = ResearchStrategy(strategy, PARAMS, candles)
    for length in range(warmup(strategy, PARAMS), len(candles)):
        prefix = ResearchStrategy(strategy, PARAMS, candles[:length])
        for holding in (False, True):
            assert prefix.decide(length-1, holding) == full.decide(length-1, holding)


def test_breakout_excludes_current_high_and_rsi_requires_recovery():
    candles = list(series([100,101,103,104]))
    candles[2] = candles[2].model_copy(update={"high": D(200)})
    assert ResearchStrategy("breakout", PARAMS, tuple(candles)).decide(2, False).action == "buy"
    falling = series([100,90,80,70,60,50,60,70])
    logic = ResearchStrategy("rsi", PARAMS, falling)
    assert all(logic.decide(i, False).action == "hold" for i in range(6))
    assert logic.decide(6, False).action == "buy"


def test_optional_filters_and_extreme_warmup():
    rising = series([100+i for i in range(40)])
    wide = tuple(c.model_copy(update={"high": c.close+D(50), "low": c.close-D(50)}) for c in rising)
    p = PARAMS.model_copy(update={"max_atr_ratio": D("0.01")})
    assert warmup("trend", p) == 14
    assert ResearchStrategy("trend", p, wide).decide(13, False).action == "hold"
    assert ResearchStrategy("trend", PARAMS, wide).decide(13, False).action == "buy"
    thin = list(rising)
    thin[20] = thin[20].model_copy(update={"volume":D(1)})
    b = PARAMS.model_copy(update={"volume_multiple":D(2)})
    assert ResearchStrategy("breakout", b, tuple(thin)).decide(20, False).action == "hold"
    assert ResearchStrategy("breakout", PARAMS, tuple(thin)).decide(20, False).action == "buy"
    for strategy, options in (("trend", p), ("breakout", b)):
        full = ResearchStrategy(strategy, options, wide)
        for n in range(warmup(strategy, options), len(wide)):
            assert ResearchStrategy(strategy, options, wide[:n]).decide(n-1, False) == full.decide(n-1, False)


def test_future_changes_do_not_change_prior_fills():
    a = series([100+(i%9) for i in range(60)])
    b = a[:40]+tuple(c.model_copy(update={"open":D(200), "high":D(200), "low":D(200), "close":D(200)}) for c in a[40:])
    cfg = CONFIG.model_copy(update={"final_policy": "mark_to_market"})
    first, second = replay(a,"trend",3,cfg), replay(b,"trend",3,cfg)
    assert [f for f in first.fills if f.candle_time < 40*3600] == [f for f in second.fills if f.candle_time < 40*3600]
    assert [p for p in first.equity if p.time <= 40*3600] == [p for p in second.equity if p.time <= 40*3600]


def test_risk_budget_exposure_precision_and_context_independence():
    cfg = CONFIG.model_copy(update={"risk_fraction":D("0.01"), "exposure_fraction":D("0.2")})
    a = replay(series([100,101,102,103,104,105]), "trend",3,cfg)
    fill = a.fills[0]
    assert fill.quantity*fill.price <= 200 and fill.quantity*(fill.price-a.trades[0].planned_stop) <= 10
    assert all(p.cash >= 0 for p in a.equity)
    with localcontext() as ctx:
        ctx.prec = 7
        assert replay(series([100,101,102,103,104,105]),"trend",3,cfg) == a


def test_minimum_rejection_and_unsellable_open_position():
    cfg = CONFIG.model_copy(update={"capital": D("0.5")})
    result = replay(series([100,100,90]), config=cfg)
    assert not result.fills and len(result.rejections) == 1
    result = replay(series([100,100,1]), rules=RULES.model_copy(update={"min_notional":D(100)}))
    assert result.portfolio.position and len(result.fills) == 1
    assert "saída" in result.rejections[0]


@pytest.mark.parametrize("change", ["open", "gap", "duplicate", "reverse"])
def test_invalid_candles_rejected(change):
    candles = list(series([100]*10))
    if change == "open": candles[5] = candles[5].model_copy(update={"closed":False})
    if change == "gap": candles.pop(5)
    if change == "duplicate": candles[5] = candles[4]
    if change == "reverse": candles.reverse()
    with pytest.raises(ValueError): replay(tuple(candles))


def test_metric_reference_gain_loss_breakeven():
    fill = Fill(side="buy",time=0,candle_time=0,decision_time=0,price=100,reference_price=100,quantity=1,fee=0,slippage_cost=0,reason="synthetic",cash_after=900)
    trades = [Trade(entry=fill,exit=fill,pnl=p,return_pct=p,planned_stop=None,planned_target=None) for p in (D(20),D(-10),D(0))]
    equity = [EquityPoint(time=i,equity=e,cash=e,quantity=0,drawdown_pct=d) for i,e,d in [(0,1000,0),(1,900,10),(2,1010,0)]]
    result = metrics(D(1000),equity,trades,[],1)
    assert result.profit_factor == 2 and result.realized_win_loss_ratio == 2
    assert result.max_drawdown_pct == 10 and result.net_return_pct == 1
    assert result.wins == result.losses == result.breakeven == 1


@pytest.fixture
def research(settings, snapshot):
    store = HistoryStore(settings.database_path)
    store.migrate()
    snapshot = snapshot.model_copy(update={"instrument": {"symbol":"BTCUSDT","status":"Trading","quote_coin":"USDT",
        "source_time_ms":1,"price_filter":{"tickSize":"0.01"},"lot_size_filter":{"basePrecision":"0.001",
        "minOrderQty":"0.001","maxMarketOrderQty":"100000","minOrderAmt":"1","maxOrderAmt":"10000000"}}})
    store.save(snapshot)
    job, _ = run_job(store, request_for(100))
    service = ResearchService(store)
    request = ProtocolRequest(dataset_hash=job["dataset_id"],strategy="buy_hold", train_start=START,
        train_end=START+40*3600,validation_end=START+70*3600,test_end=START+100*3600)
    return service, request


def test_protocol_persistence_replay_splits_and_immutability(research):
    service, spec = research
    protocol = service.freeze(spec)
    assert service.freeze(spec)["id"] == protocol["id"]
    with pytest.raises(ResearchError, match="TEST_REQUIRES"):
        service.run(RunRequest(protocol_id=protocol["id"],partition="test"))
    for partition in ("train","validation","test"):
        result = service.run(RunRequest(protocol_id=protocol["id"],partition=partition))
        assert service.verify(result["id"])["identical"]
        assert service.result(result["id"]) == result
        assert result["simulation"] == result["benchmark"]
        assert result["simulation"]["fills"][0]["time"] == result["manifest"]["start_time"]+3600
    with pytest.raises(sqlite3.IntegrityError):
        with service.store.connect() as db: db.execute("UPDATE research_runs SET payload='{}'")
    with pytest.raises(sqlite3.IntegrityError):
        with service.store.connect() as db: db.execute("DELETE FROM research_protocols")


def test_tampered_dataset_and_results_rejected(research):
    service, spec = research
    protocol = service.freeze(spec)
    result = service.run(RunRequest(protocol_id=protocol["id"],partition="train"))
    with service.store.connect() as db:
        db.execute("DROP TRIGGER research_runs_no_update")
        db.execute("UPDATE research_runs SET payload='{}'")
    with pytest.raises(ResearchError, match="HASH_MISMATCH"): service.result(result["id"])
    with service.store.connect() as db:
        trigger = db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='historical_datasets' AND sql LIKE '%UPDATE%'").fetchone()[0]
        db.execute(f'DROP TRIGGER "{trigger}"')
        db.execute("UPDATE historical_datasets SET payload='{}'")
    with pytest.raises(HistoryError): service.run(RunRequest(protocol_id=protocol["id"],partition="train"))


def test_research_api_validation_intent_origin_and_flow(research, settings):
    service, spec = research
    headers = {"X-CryptoLab-Research":"1"}
    with TestClient(create_app(settings)) as client:
        url = "/api/v1/research/protocols"
        assert client.post(url,json=spec.model_dump(mode="json")).status_code == 403
        assert client.post(url,json=spec.model_dump(mode="json"),headers={**headers,"Origin":"https://evil.invalid"}).status_code == 403
        assert client.post(url,json={**spec.model_dump(mode="json"),"strategy":"mack"},headers=headers).status_code == 422
        protocol = client.post(url,json=spec.model_dump(mode="json"),headers=headers).json()
        response = client.post("/api/v1/research/runs",json={"protocol_id":protocol["id"],"partition":"train"},headers=headers)
        assert response.status_code == 200
        result = response.json()
        assert isinstance(result["simulation"]["metrics"]["pnl"],str)
        assert client.get(f'/api/v1/research/runs/{result["id"]}').json() == result
        assert client.post(f'/api/v1/research/runs/{result["id"]}/verify',headers=headers).json()["identical"]
        assert client.post("/api/v1/orders",json={},headers=headers).status_code == 404
