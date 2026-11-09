"""Execução virtual sintética, offline; não representa uma negociação real."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D, ROUND_UP, localcontext
import json
import os
import sqlite3
import socket
import subprocess
import sys

import pytest

from cryptolab.config import INTERVALS
from cryptolab.models import Candle
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.models import MonitorConfig
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.executor_models import VirtualExecutionRequest, VirtualFillEvidence
from cryptolab.paper.marking import ExecutionError, PaperMarker
from cryptolab.paper.ledger import LEDGER_CONTEXT
from cryptolab.paper.models import StateRecord, WalletSpec
from cryptolab.paper.decisions import DecisionError
from cryptolab.paper.planner import VirtualTradePlanner
from cryptolab.storage import canonical_dataset
from test_paper_decisions import services, active, record
from test_paper_planner import setup_planner, positioned_scenario


@pytest.fixture(autouse=True)
def only_paper(monkeypatch):
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED","true")
    monkeypatch.setenv("LIVE_TRADING_ENABLED","false")


def executor(s):
    return PaperExecutor(s[0].path,clock=lambda:s[7][0])


def req(item,key="virtual-one"):
    return VirtualExecutionRequest(decision_id=item["id"],idempotency_key=key)


def test_buy_is_atomic_decimal_and_recovered(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=s[1].wallet(s[5]["wallet_id"])
    result=executor(s).execute(req(item),paper=True)
    event=result["ledger_event"]; p=result["evidence"]["proposal"]
    quantity,price,fee=D(p["planned_quantity"]),D(p["estimated_price"]),D(event["payload"]["input"]["fee"])
    assert result["status"] == "CONSUMED" and result["receipt_mode"] == "NEW_VIRTUAL_FILL"
    assert D(event["payload"]["after"]["cash"]) == D(before["state"]["cash"])-quantity*price-fee
    assert D(event["payload"]["after"]["quantity"]) == quantity
    assert D(event["payload"]["after"]["acquisition_cost"]) == quantity*price+fee
    assert D(p["estimated_slippage"]) == (price-D(p["reference_price"]))*quantity
    assert price == D("180.09")
    assert fee == (quantity*price*D("0.001")).quantize(D("0.000000000000000001"),rounding=ROUND_UP)
    assert event["payload"]["input"]["candle_time"] == item["proposal"]["earliest_fill_candle"]
    assert result["evidence"]["protection"]["automatic_monitoring"] is False
    assert result["evidence"]["protection"]["stop"] == "174.68" and result["evidence"]["protection"]["target"] == "190.9"
    assert D(p["planned_risk"]) <= D("10")
    ticker=s[2].ticker.model_copy(update={"price":s[2].ticker.price+1})
    s[0].save(s[2].model_copy(update={"ticker":ticker}))
    recovered=executor(s).execute(req(item),paper=True)
    assert recovered["execution_id"] == result["execution_id"] and recovered["ledger_event"] == event
    assert recovered["receipt_mode"] == "RECOVER_VIRTUAL_FILL"
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]) == 1
    with pytest.raises(ExecutionError,match="EXECUTION_CONFLICT"):
        executor(s).execute(req(item,"other-key"),paper=True)


def test_guards_and_paused(services,monkeypatch):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=s[1].wallet(s[5]["wallet_id"])
    with pytest.raises(ExecutionError,match="EXPLICIT_PAPER_REQUIRED"):
        executor(s).execute(req(item))
    monkeypatch.delenv("PAPER_SIMULATION_ENABLED",raising=False)
    with pytest.raises(ExecutionError,match="PAPER_SIMULATION_DISABLED"):
        executor(s).execute(req(item),paper=True)
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED","true")
    s[1].append(s[5]["wallet_id"],"pause",StateRecord(state="paused",event_time=2))
    with pytest.raises(ExecutionError,match="WALLET_PAUSED"):
        executor(s).execute(req(item),paper=True)
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]) == 0
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError): executor(s).execute(req(item),paper=True)


def test_binary_float_candles_are_rejected(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    with s[0].connect() as db:
        row=db.execute("SELECT payload FROM snapshots WHERE symbol='BTCUSDT' AND interval='60'").fetchone()
        snapshot=json.loads(row[0]); snapshot["candles"][0]["open"]=100.0
        db.execute("UPDATE snapshots SET payload=? WHERE symbol='BTCUSDT' AND interval='60'",(json.dumps(snapshot),))
    with pytest.raises(ExecutionError,match="FLOAT_MARKET_DATA_REJECTED"):
        executor(s).execute(req(item),paper=True)
    assert not [e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]


def test_missing_public_price_never_creates_fill(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    with s[0].connect() as db:
        row=db.execute("SELECT payload FROM snapshots WHERE symbol='BTCUSDT' AND interval='60'").fetchone()
        snapshot=json.loads(row[0]); snapshot["ticker"].pop("price")
        db.execute("UPDATE snapshots SET payload=? WHERE symbol='BTCUSDT' AND interval='60'",(json.dumps(snapshot),))
    before=s[1].wallet(s[5]["wallet_id"])
    with pytest.raises(ExecutionError,match="SNAPSHOT_INVALID"):
        executor(s).execute(req(item),paper=True)
    assert s[1].wallet(s[5]["wallet_id"]) == before


def test_contract_rejects_nested_float_financial_data(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    result=executor(s).execute(req(item),paper=True)
    body=dict(result["evidence"]); proposal=dict(body["proposal"]); risk=dict(proposal["risk"])
    costs=dict(risk["costs"]); costs["fee_rate"]=0.001; risk["costs"]=costs; proposal["risk"]=risk; body["proposal"]=proposal
    with pytest.raises(ValueError,match="strings ou Decimal"):
        VirtualFillEvidence.model_validate(body)


def test_rollback_when_evidence_insert_fails(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=s[1].wallet(s[5]["wallet_id"]); events=s[1].events(s[5]["wallet_id"])
    with s[0].connect() as db:
        db.execute("CREATE TRIGGER abort_test BEFORE INSERT ON paper_execution_evidence BEGIN SELECT RAISE(ABORT,'simulated'); END")
    with pytest.raises(ExecutionError,match="EXECUTION_CONFLICT"):
        executor(s).execute(req(item),paper=True)
    assert s[1].wallet(s[5]["wallet_id"]) == before and s[1].events(s[5]["wallet_id"]) == events
    with s[0].connect() as db: db.execute("DROP TRIGGER abort_test")
    assert executor(s).execute(req(item),paper=True)["status"] == "CONSUMED"


def test_concurrent_processes_execute_once(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    script=("import json,sys,socket; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN')); "
        "from pathlib import Path; from cryptolab.paper.executor import PaperExecutor; "
        "from cryptolab.paper.executor_models import VirtualExecutionRequest; "
        "s=PaperExecutor(Path(sys.argv[1]),clock=lambda:int(sys.argv[4])); "
        "print(json.dumps(s.execute(VirtualExecutionRequest(decision_id=sys.argv[2],idempotency_key=sys.argv[3]),paper=True)['execution_id']))")
    args=[sys.executable,"-c",script,str(s[0].path),item["id"],"process-key",str(s[7][0])]
    def run(_): return json.loads(subprocess.run(args,text=True,capture_output=True,check=True,timeout=30).stdout)
    with ThreadPoolExecutor(max_workers=3) as pool: ids=list(pool.map(run,range(3)))
    assert len(set(ids)) == 1
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]) == 1


def test_invalidated_expired_and_binding_disabled(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    service.invalidate_decision(item["id"],"REVIEW")
    with pytest.raises(ExecutionError,match="DECISION_NOT_RECORDED"): executor(s).execute(req(item),paper=True)


@pytest.mark.parametrize("problem",["expired","disabled","stale","future","gap","clock"])
def test_refuse_unsafe_state_without_fill(services,problem):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    if problem == "expired": s[7][0]=item["proposal"]["expires_at"]*1000
    elif problem == "disabled": service.disable_binding(binding["id"],"STOP")
    elif problem == "stale": s[7][0]+=91000
    elif problem == "clock": s[7][0]-=1000
    elif problem == "future":
        ticker=s[2].ticker.model_copy(update={"source_time_ms":s[7][0]+1000})
        s[0].save(s[2].model_copy(update={"ticker":ticker}))
    elif problem == "gap":
        candles=list(s[2].candles); candles.pop(10)
        s[0].save(s[2].model_copy(update={"candles":candles,"dataset_id":canonical_dataset("BTCUSDT","60",candles)[0]}))
    with pytest.raises(ExecutionError): executor(s).execute(req(item),paper=True)
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]) == 0


def test_new_execution_reprices_at_fresh_public_ticker(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    ticker=s[2].ticker.model_copy(update={"price":s[2].ticker.price+1})
    s[0].save(s[2].model_copy(update={"ticker":ticker}))
    result=executor(s).execute(req(item),paper=True)
    assert result["evidence"]["proposal"]["reference_price"] == str(ticker.price)
    assert result["evidence"]["snapshot_hash"] != item["proposal"]["snapshot_hash"]


def test_instrument_minimum_blocks_without_fill(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    raw=dict(s[2].instrument); lots=dict(raw["lot_size_filter"]); lots["minOrderAmt"]="99999"; raw["lot_size_filter"]=lots
    s[0].save(s[2].model_copy(update={"instrument":raw}))
    with pytest.raises(ExecutionError,match="INSUFFICIENT_BALANCE_OR_INSTRUMENT_MINIMUM"):
        executor(s).execute(req(item),paper=True)
    assert not [e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]


def test_hold_does_not_create_fill(services):
    s,service=services
    _,signal,wallet,binding=positioned_scenario(s,strategy="buy_hold")
    registered=service.register_binding(binding); service.activate_binding(registered["id"])
    proposal=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    item=service.record_decision(registered["id"],signal["id"],proposal["validation_hash"])
    before=s[1].events(wallet["wallet_id"])
    with pytest.raises(ExecutionError,match="HOLD_NOT_EXECUTABLE"): executor(s).execute(req(item),paper=True)
    assert s[1].events(wallet["wallet_id"]) == before


def test_buy_hold_entry_remains_blocked(services):
    s,service=services
    config=MonitorConfig(bot_id="hold-entry",symbol="BTCUSDT",interval="60",strategy="buy_hold")
    signal=MonitorRuntime(s[0],clock=lambda:s[7][0]).once(config)
    wallet=s[1].create_wallet(WalletSpec(bot_id=config.bot_id,strategy="buy_hold",symbol="BTCUSDT",interval="60",initial_capital="1000",opened_at=0),"hold-entry-create")
    s[1].append(wallet["wallet_id"],"active",StateRecord(state="active",event_time=1))
    binding={"wallet_id":wallet["wallet_id"],"wallet_hash":wallet["wallet_hash"],"monitor_config_hash":signal["config_hash"],"risk":s[6]["risk"]}
    registered=service.register_binding(binding); service.activate_binding(registered["id"])
    proposal=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    assert proposal["status"] == "BUY_HOLD_POLICY_REQUIRED" and proposal["planned_stop"] is None
    before=s[1].events(wallet["wallet_id"])
    with pytest.raises(DecisionError,match="PROPOSAL_NOT_RECORDABLE"):
        service.record_decision(registered["id"],signal["id"],proposal["validation_hash"])
    assert s[1].events(wallet["wallet_id"]) == before


def test_tampered_execution_and_missing_evidence_detected(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    result=executor(s).execute(req(item),paper=True)
    assert executor(s).verify_integrity()["executions"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        with s[0].connect() as db: db.execute("UPDATE paper_execution_evidence SET payload='{}'")
    with s[0].connect() as db:
        db.execute("DROP TRIGGER paper_execution_evidence_no_update")
        db.execute("UPDATE paper_execution_evidence SET payload='{}' WHERE id=?",(result["execution_id"],))
    with pytest.raises(ExecutionError,match="EXECUTION_INTEGRITY_ERROR"):
        executor(s).receipt(result["execution_id"])


def test_process_crash_before_and_after_commit(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=s[1].wallet(s[5]["wallet_id"])
    script='''import os,sys,socket
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("NETWORK_FORBIDDEN"))
from pathlib import Path
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.executor_models import VirtualExecutionRequest
s=PaperExecutor(Path(sys.argv[1]),clock=lambda:int(sys.argv[4]))
old=s.service.paper.append_in_transaction
def crash(*args):
    old(*args)
    os._exit(76)
s.service.paper.append_in_transaction=crash
s.execute(VirtualExecutionRequest(decision_id=sys.argv[2],idempotency_key=sys.argv[3]),paper=True)
'''
    args=[sys.executable,"-c",script,str(s[0].path),item["id"],"crash-key",str(s[7][0])]
    assert subprocess.run(args,capture_output=True,timeout=30).returncode == 76
    assert s[1].wallet(s[5]["wallet_id"]) == before and executor(s).verify_integrity()["executions"] == 0
    args[2]=("import os,sys,socket; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN')); "
        "from pathlib import Path; from cryptolab.paper.executor import PaperExecutor; "
        "from cryptolab.paper.executor_models import VirtualExecutionRequest; "
        "s=PaperExecutor(Path(sys.argv[1]),clock=lambda:int(sys.argv[4])); "
        "s.execute(VirtualExecutionRequest(decision_id=sys.argv[2],idempotency_key=sys.argv[3]),paper=True); os._exit(77)")
    assert subprocess.run(args,capture_output=True,timeout=30).returncode == 77
    result=executor(s).execute(req(item,"crash-key"),paper=True)
    assert result["receipt_mode"] == "RECOVER_VIRTUAL_FILL"
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "fill"]) == 1


def test_expiry_during_execution_rolls_back(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=s[1].wallet(s[5]["wallet_id"])
    times=iter([s[7][0],s[7][0],item["proposal"]["expires_at"]*1000])
    delayed=PaperExecutor(s[0].path,clock=lambda:next(times))
    with pytest.raises(ExecutionError,match="DECISION_EXPIRED_DURING_EXECUTION"):
        delayed.execute(req(item),paper=True)
    assert s[1].wallet(s[5]["wallet_id"]) == before and executor(s).verify_integrity()["executions"] == 0


def test_cli_requires_explicit_paper_and_returns_virtual_receipt(services,monkeypatch,capsys):
    from cryptolab.paper.executor_cli import main
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    monkeypatch.setenv("CRYPTOLAB_DATABASE",str(s[0].path))
    monkeypatch.setattr("cryptolab.paper.decisions.time.time",lambda:s[7][0]/1000)
    def call(*args):
        monkeypatch.setattr("sys.argv",["executor",*args]); code=main()
        return code,json.loads(capsys.readouterr().out)
    code,denied=call("once","--decision",item["id"],"--key","cli-key")
    assert code == 1 and denied["error"] == "EXPLICIT_PAPER_REQUIRED"
    code,done=call("once","--decision",item["id"],"--key","cli-key","--paper")
    assert code == 0 and done["status"] == "CONSUMED" and done["live_execution_enabled"] is False
    code,receipt=call("show","--execution",done["execution_id"])
    assert code == 0 and receipt["execution_id"] == done["execution_id"]
    assert call("verify")[1]["valid"] is True


def test_executor_never_reads_private_credentials_or_connects(services,monkeypatch):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    original_getenv=os.getenv
    def guarded_getenv(name,*args):
        if name in ("BYBIT_API_KEY","BYBIT_API_SECRET"):
            raise AssertionError("PRIVATE_CREDENTIAL_ACCESSED")
        return original_getenv(name,*args)
    def blocked(*args,**kwargs):
        raise AssertionError("NETWORK_FORBIDDEN")
    monkeypatch.setattr(os,"getenv",guarded_getenv)
    monkeypatch.setattr(socket.socket,"connect",blocked)
    assert executor(s).execute(req(item),paper=True)["status"] == "CONSUMED"


@pytest.mark.parametrize("max_qty",["100","0.5"])
def test_buy_sell_integration_and_pnl(services,max_qty):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    buy=executor(s).execute(req(item,"buy-1"),paper=True)
    buy_event=buy["ledger_event"]; quantity=D(buy_event["payload"]["input"]["quantity"])
    snap=s[2]; step=INTERVALS["60"]; previous=list(snap.candles[:-1]); last=previous[-1]
    next_closed=last.model_copy(update={"time":last.time+step,"open":D(150),"high":D(151),"low":D(149),"close":D(150),"closed":True})
    later_open=next_closed.model_copy(update={"time":next_closed.time+step,"closed":False})
    candles=previous+[next_closed,later_open]
    s[7][0]+=step*1000
    ticker=snap.ticker.model_copy(update={"price":D(150),"source_time_ms":s[7][0]})
    instrument={**snap.instrument,"source_time_ms":s[7][0],
                "lot_size_filter":{**snap.instrument["lot_size_filter"],"maxMarketOrderQty":max_qty}}
    changed=snap.model_copy(update={"candles":candles,"ticker":ticker,"instrument":instrument,
        "dataset_id":canonical_dataset("BTCUSDT","60",candles)[0],"source_time_ms":s[7][0],"fetched_at_ms":s[7][0]})
    s[0].save(changed)
    signal=MonitorRuntime(s[0],clock=lambda:s[7][0]).once(s[3])
    mark=PaperMarker(s[0].path,clock=lambda:s[7][0]).mark(binding["id"],signal["id"],"mark-after-buy")
    assert mark["price"] == "150" and mark["event_id"]
    proposal=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(s[5]["wallet_id"],signal["id"],s[6])
    assert proposal["action"] == "SELL"
    sale=service.record_decision(binding["id"],signal["id"],proposal["validation_hash"])
    result=executor(s).execute(req(sale,"sell-1"),paper=True)
    event=result["ledger_event"]; sold=D(event["payload"]["input"]["quantity"])
    assert D(event["payload"]["input"]["price"]) == D("149.92")
    with localcontext(LEDGER_CONTEXT):
        proceeds=sold*D(event["payload"]["input"]["price"])-D(event["payload"]["input"]["fee"])
        cost=D(buy_event["payload"]["after"]["acquisition_cost"])
        allocated=cost if sold == quantity else cost*sold/quantity
        assert D(event["payload"]["after"]["realized_pnl"]) == proceeds-allocated
        assert D(event["payload"]["after"]["quantity"]) == quantity-sold
    if max_qty == "0.5":
        assert sold == D("0.5")
        assert result["evidence"]["protection"]["source_execution"] == buy["execution_id"]
        assert result["evidence"]["protection"]["previous_protection"] == buy["evidence"]["protection"]
    else:
        assert sold == quantity
    assert result["evidence"]["mark_id"] == mark["id"]
    assert executor(s).execute(req(sale,"sell-1"),paper=True)["execution_id"] == result["execution_id"]
    assert len(executor(s).history(s[5]["wallet_id"])) == 2
