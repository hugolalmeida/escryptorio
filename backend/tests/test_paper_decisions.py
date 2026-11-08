"""Testes isolados com dados sintéticos; nenhum executor ou acesso de rede."""
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from cryptolab.monitor.models import MonitorConfig
from cryptolab.engine.contracts import StrategyParameters
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.service import MonitorService, digest
from cryptolab.paper.decisions import DecisionError, DecisionService
from cryptolab.paper.models import MarkRecord, StateRecord
from cryptolab.paper.planner import VirtualTradePlanner
from test_paper_planner import setup_planner, tables, plan, positioned_scenario


@pytest.fixture
def services(setup_planner):
    s = setup_planner
    service = DecisionService(s[0].path,clock=lambda:s[7][0])
    return s,service


def active(s, service):
    registered = service.register_binding(s[6])
    return service.activate_binding(registered["id"])


def record(s, service, binding):
    proposed = plan(s)
    return service.record_decision(binding["id"],s[4]["id"],proposed["validation_hash"])


def test_lifecycle_binding_decision_idempotency_and_ledger(services):
    s,service=services
    before=tables(s[0])
    binding=service.register_binding(s[6])
    assert binding["state"] == "REGISTERED" and service.register_binding(s[6])["id"] == binding["id"]
    assert service.activate_binding(binding["id"])["state"] == "ACTIVE"
    first=record(s,service,binding)
    assert first["state"] == "RECORDED" and first["proposal"]["action"] == "BUY"
    assert record(s,service,binding)["id"] == first["id"]
    assert DecisionService(s[0].path,clock=lambda:s[7][0]).get_decision(first["id"])["id"] == first["id"]
    assert service.verify_integrity() == {"valid":True,"bindings":1,"decisions":1,"execution_enabled":False}
    assert tables(s[0]) == before
    disabled=service.disable_binding(binding["id"],"OPERATOR_STOP")
    assert disabled["state"] == "DISABLED" and disabled["events"][-1]["reason"] == "OPERATOR_STOP"
    assert tables(s[0]) == before
    with pytest.raises(DecisionError,match="BINDING_TRANSITION_INVALID"): service.activate_binding(binding["id"])


def test_conflicting_bindings_and_explicit_replacement(services):
    s,service=services
    first=active(s,service)
    s[6]["risk"]["risk_fraction"]="0.02"
    second=service.register_binding(s[6])
    assert second["version"] == 2 and second["state"] == "REGISTERED"
    with pytest.raises(DecisionError,match="BINDING_ACTIVE_CONFLICT"): service.activate_binding(second["id"])
    service.disable_binding(first["id"],"POLICY_CHANGE")
    assert service.activate_binding(second["id"])["state"] == "ACTIVE"
    assert service.get_binding(first["id"])["state"] == "DISABLED"


def test_binding_rejects_bad_wallet_or_configuration(services):
    s,service=services
    s[6]["wallet_hash"]="0"*64
    with pytest.raises(DecisionError,match="BINDING_WALLET_MISMATCH"): service.register_binding(s[6])
    s[6]["wallet_hash"]=s[5]["wallet_hash"]
    s[6]["monitor_config_hash"]="0"*64
    with pytest.raises(DecisionError,match="MONITOR_CONFIG_NOT_FOUND"): service.register_binding(s[6])


def test_changed_ledger_rejects_old_plan(services):
    s,service=services
    binding=active(s,service)
    old=plan(s)
    s[1].append(s[5]["wallet_id"],"fixture-mark",MarkRecord(price=str(s[2].ticker.price),candle_time=s[4]["decision_time"],event_time=s[7][0]//1000))
    before=tables(s[0])
    with pytest.raises(DecisionError,match="PROPOSAL_CHANGED"):
        service.record_decision(binding["id"],s[4]["id"],old["validation_hash"])
    assert tables(s[0]) == before and service.verify_integrity()["decisions"] == 0


def test_conflict_same_candle_after_binding_change(services):
    s,service=services
    first=active(s,service)
    original=record(s,service,first)
    service.disable_binding(first["id"],"CHANGE_RISK")
    s[6]["risk"]["risk_fraction"]="0.02"
    other=service.register_binding(s[6]); service.activate_binding(other["id"])
    with pytest.raises(DecisionError,match="DECISION_CONFLICT"):
        record(s,service,other)
    assert service.get_decision(original["id"])["id"] == original["id"]


def test_database_enforces_one_decision_per_wallet_candle(services):
    s,service=services
    binding=active(s,service); decision=record(s,service,binding)
    config=s[3].model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    other=MonitorRuntime(s[0],clock=lambda:s[7][0]).once(config)
    assert other["id"] != s[4]["id"] and other["candle_time"] == s[4]["candle_time"]
    with pytest.raises(sqlite3.IntegrityError):
        with s[0].connect() as db:
            row=db.execute("SELECT * FROM paper_decisions WHERE id=?",(decision["id"],)).fetchone()
            db.execute("INSERT INTO paper_decisions VALUES (?,?,?,?,?,?,?)",("0"*64,row["wallet_id"],row["binding_id"],other["id"],other["config_hash"],row["candle_time"],row["payload"]))


def test_incomplete_proposal_not_recorded(services):
    s,service=services
    s[0].save(s[2].model_copy(update={"candles":s[2].candles[:-1]}))
    binding=active(s,service); proposal=plan(s)
    assert proposal["status"] == "AWAITING_NEXT_OPEN"
    with pytest.raises(DecisionError,match="PROPOSAL_NOT_RECORDABLE"):
        service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    assert service.verify_integrity()["decisions"] == 0


def test_invalidation_expiry_and_clock_rewind(services):
    s,service=services
    binding=active(s,service); item=record(s,service,binding)
    invalid=service.invalidate_decision(item["id"],"MANUAL_REVIEW")
    assert invalid["state"] == "INVALIDATED" and invalid["events"][-1]["reason"] == "MANUAL_REVIEW"
    assert service.get_decision(item["id"])["state"] == "INVALIDATED"
    recovered=record(s,service,binding)
    assert recovered["id"] == item["id"] and recovered["state"] == "INVALIDATED"
    assert recovered["receipt_mode"] == "RECOVER_EXISTING_RECEIPT" and recovered["execution_enabled"] is False


def test_expiry_persisted_and_cannot_rewind(services):
    s,service=services
    item=record(s,service,active(s,service))
    s[7][0]=item["proposal"]["expires_at"]*1000
    expired=service.get_decision(item["id"])
    assert expired["state"] == "EXPIRED" and expired["events"][-1]["reason"] == "SIGNAL_EXPIRED"
    s[7][0]-=1000
    with pytest.raises(DecisionError,match="CLOCK_ROLLBACK"): service.get_decision(item["id"])


def test_expiry_observed_on_repeat_is_committed(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    item=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    s[7][0]=item["proposal"]["expires_at"]*1000
    recovered=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    assert recovered["id"] == item["id"] and recovered["state"] == "EXPIRED"
    s[7][0]-=1000
    with pytest.raises(DecisionError,match="CLOCK_ROLLBACK"):
        service.get_decision(item["id"])
    s[7][0]+=1000
    assert service.get_decision(item["id"])["state"] == "EXPIRED"


def test_stale_snapshot_and_paused_wallet_fail_closed(services):
    s,service=services
    binding=active(s,service); proposed=plan(s)
    s[1].append(s[5]["wallet_id"],"pause",StateRecord(state="paused",event_time=2))
    with pytest.raises(DecisionError,match="WALLET_PAUSED"):
        service.record_decision(binding["id"],s[4]["id"],proposed["validation_hash"])
    s[1].append(s[5]["wallet_id"],"resume",StateRecord(state="active",event_time=3))
    s[7][0]+=91000
    with pytest.raises(DecisionError,match="STALE_SNAPSHOT"):
        service.record_decision(binding["id"],s[4]["id"],proposed["validation_hash"])
    assert service.verify_integrity()["decisions"] == 0


def test_tamper_and_checkpoint_integrity(services):
    s,service=services
    binding=active(s,service); item=record(s,service,binding)
    with pytest.raises(sqlite3.IntegrityError):
        with s[0].connect() as db: db.execute("UPDATE paper_decisions SET payload='{}'")
    with s[0].connect() as db:
        db.execute("UPDATE paper_decision_heads SET event_hash=? WHERE decision_id=?",("0"*64,item["id"]))
    with pytest.raises(DecisionError,match="CHECKPOINT_INTEGRITY_ERROR"):
        service.get_decision(item["id"])


def test_rollback_before_commit_and_restart(services,monkeypatch):
    s,service=services
    binding=active(s,service); proposed=plan(s); original=service._event
    def crash(db,entity,identifier,kind,now,reason=None):
        original(db,entity,identifier,kind,now,reason)
        if entity == "decision": raise RuntimeError("simulated crash")
    monkeypatch.setattr(service,"_event",crash)
    before=tables(s[0])
    with pytest.raises(RuntimeError,match="simulated crash"):
        service.record_decision(binding["id"],s[4]["id"],proposed["validation_hash"])
    restarted=DecisionService(s[0].path,clock=lambda:s[7][0])
    assert restarted.verify_integrity()["decisions"] == 0 and tables(s[0]) == before
    assert restarted.record_decision(binding["id"],s[4]["id"],proposed["validation_hash"])["state"] == "RECORDED"


def test_process_crash_before_commit_recovers(services):
    s,service=services
    binding=active(s,service); proposal=plan(s); before=tables(s[0])
    script = '''import os,sys
from pathlib import Path
from cryptolab.paper.decisions import DecisionService
s=DecisionService(Path(sys.argv[1]),clock=lambda:int(sys.argv[5]))
old=s._event
def crash(db,entity,identifier,kind,now,reason=None):
    old(db,entity,identifier,kind,now,reason)
    if entity == "decision": os._exit(73)
s._event=crash
s.record_decision(sys.argv[2],sys.argv[3],sys.argv[4])
'''
    args=[sys.executable,"-c",script,str(s[0].path),binding["id"],s[4]["id"],proposal["validation_hash"],str(s[7][0])]
    result=subprocess.run(args,text=True,capture_output=True,timeout=30)
    assert result.returncode == 73
    restarted=DecisionService(s[0].path,clock=lambda:s[7][0])
    assert restarted.verify_integrity()["decisions"] == 0 and tables(s[0]) == before
    assert restarted.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])["state"] == "RECORDED"


def test_concurrent_processes_same_decision(services):
    s,service=services
    binding=active(s,service); proposed=plan(s); before=tables(s[0])
    script = ("import json,sys; from pathlib import Path; from cryptolab.paper.decisions import DecisionService; "
              "s=DecisionService(Path(sys.argv[1]),clock=lambda:int(sys.argv[5])); "
              "print(json.dumps(s.record_decision(sys.argv[2],sys.argv[3],sys.argv[4])['id']))")
    args=[sys.executable,"-c",script,str(s[0].path),binding["id"],s[4]["id"],proposed["validation_hash"],str(s[7][0])]
    def run(_):
        result=subprocess.run(args,text=True,capture_output=True,check=True,timeout=30)
        return json.loads(result.stdout)
    with ThreadPoolExecutor(max_workers=3) as pool:
        ids=list(pool.map(run,range(3)))
    assert len(set(ids)) == 1 and service.verify_integrity()["decisions"] == 1
    assert tables(s[0]) == before


def test_commit_without_response_recovers_after_ticker_change_across_processes(services):
    s,service=services
    binding=active(s,service); proposal=plan(s); before=tables(s[0])
    script = ("import os,sys; from pathlib import Path; from cryptolab.paper.decisions import DecisionService; "
              "s=DecisionService(Path(sys.argv[1]),clock=lambda:int(sys.argv[5])); "
              "s.record_decision(sys.argv[2],sys.argv[3],sys.argv[4]); os._exit(74)")
    args=[sys.executable,"-c",script,str(s[0].path),binding["id"],s[4]["id"],proposal["validation_hash"],str(s[7][0])]
    stopped=subprocess.run(args,text=True,capture_output=True,timeout=30)
    assert stopped.returncode == 74 and not stopped.stdout
    with s[0].connect() as db:
        original=db.execute("SELECT id FROM paper_decisions").fetchone()[0]
    ticker=s[2].ticker.model_copy(update={"price":s[2].ticker.price+Decimal("0.1"), "source_time_ms":s[7][0]+1000})
    s[7][0]+=1000
    s[0].save(s[2].model_copy(update={"ticker":ticker,"fetched_at_ms":s[7][0],"source_time_ms":s[7][0]}))
    assert plan(s)["validation_hash"] != proposal["validation_hash"]
    retry=("import json,sys; from pathlib import Path; from cryptolab.paper.decisions import DecisionService; "
           "s=DecisionService(Path(sys.argv[1]),clock=lambda:int(sys.argv[5])); "
           "print(json.dumps(s.record_decision(sys.argv[2],sys.argv[3],sys.argv[4])))")
    args[2]=retry; args[7]=str(s[7][0])
    def run(_):
        return json.loads(subprocess.run(args,text=True,capture_output=True,check=True,timeout=30).stdout)
    with ThreadPoolExecutor(max_workers=2) as pool:
        recovered=list(pool.map(run,range(2)))
    assert all(r["id"] == original and r["receipt_mode"] == "RECOVER_EXISTING_RECEIPT" for r in recovered)
    assert all(r["state"] == "RECORDED" and r["execution_enabled"] is False and r["needs_revalidation"] is True for r in recovered)
    assert service.verify_integrity()["decisions"] == 1 and tables(s[0]) == before


def test_recovery_after_ledger_change_pause_and_binding_disabled(services,monkeypatch):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    original=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    s[1].append(s[5]["wallet_id"],"fixture-mark",MarkRecord(price=str(s[2].ticker.price),candle_time=s[4]["decision_time"],event_time=s[7][0]//1000))
    s[1].append(s[5]["wallet_id"],"fixture-pause",StateRecord(state="paused",event_time=s[7][0]//1000))
    service.disable_binding(binding["id"],"MANUAL_STOP")
    before=tables(s[0])
    monkeypatch.setattr(service,"_calculate",lambda *args: pytest.fail("Recuperação não pode recalcular"))
    recovered=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    assert recovered["id"] == original["id"] and recovered["state"] == "RECORDED"
    assert recovered["receipt_mode"] == "RECOVER_EXISTING_RECEIPT" and recovered["execution_enabled"] is False
    assert recovered["needs_revalidation"] is True and recovered["binding_state"] == "DISABLED"
    assert recovered["wallet_state"] == "paused" and recovered["wallet_sequence_current"] > original["proposal"]["wallet_sequence"]
    assert tables(s[0]) == before


def test_recovery_rejects_other_hash_and_different_signal(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    original=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    before=tables(s[0])
    with pytest.raises(DecisionError,match="DECISION_CONFLICT"):
        service.record_decision(binding["id"],s[4]["id"],"0"*64)
    config=s[3].model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    other=MonitorRuntime(s[0],clock=lambda:s[7][0]).once(config)
    with pytest.raises(DecisionError,match="DECISION_CONFLICT"):
        service.record_decision(binding["id"],other["id"],proposal["validation_hash"])
    assert service.get_decision(original["id"])["id"] == original["id"] and tables(s[0]) == before


def test_recovery_conflict_observes_expiry_and_cannot_rewind(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    item=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    s[7][0]=item["proposal"]["expires_at"]*1000
    with pytest.raises(DecisionError,match="DECISION_CONFLICT"):
        service.record_decision(binding["id"],s[4]["id"],"0"*64)
    assert service.get_decision(item["id"])["state"] == "EXPIRED"
    s[7][0]-=1000
    with pytest.raises(DecisionError,match="CLOCK_ROLLBACK"):
        service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])


def test_failed_new_request_preserves_observed_clock(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    item=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    s[7][0]=item["proposal"]["expires_at"]*1000
    with pytest.raises(DecisionError,match="SIGNAL_NOT_FOUND"):
        service.record_decision(binding["id"],"0"*64,proposal["validation_hash"])
    s[7][0]-=1000
    with pytest.raises(DecisionError,match="CLOCK_ROLLBACK"):
        service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])


@pytest.mark.parametrize("tamper",["payload","checkpoint"])
def test_recovery_rejects_tampering(services,tamper):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    item=service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    with s[0].connect() as db:
        if tamper == "payload":
            db.execute("DROP TRIGGER paper_decisions_no_update")
            db.execute("UPDATE paper_decisions SET payload='{}' WHERE id=?",(item["id"],))
        else:
            db.execute("UPDATE paper_decision_heads SET event_hash=? WHERE decision_id=?",("0"*64,item["id"]))
    with pytest.raises(DecisionError,match="INTEGRITY_ERROR"):
        service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])


def test_market_snapshot_changed_between_plan_and_record(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    ticker=s[2].ticker.model_copy(update={"high_24h":s[2].ticker.high_24h+1})
    s[0].save(s[2].model_copy(update={"ticker":ticker}))
    with pytest.raises(DecisionError,match="PROPOSAL_CHANGED"):
        service.record_decision(binding["id"],s[4]["id"],proposal["validation_hash"])
    assert service.verify_integrity()["decisions"] == 0


def test_legacy_and_recovered_signals_are_refused(services):
    s,service=services
    binding=active(s,service); proposal=plan(s)
    legacy=MonitorService(s[0]).evaluate(s[3],s[7][0])
    with pytest.raises(DecisionError,match="UNSUPPORTED_SIGNAL_SCHEMA"):
        service.record_decision(binding["id"],legacy["id"],proposal["validation_hash"])
    signal=dict(s[4]); signal.pop("id"); signal["origin"]="historical_recovered"; signal["eligible_for_future_paper_analysis"]=False
    identifier,payload=digest(signal)
    with s[0].connect() as db:
        db.execute("DROP TRIGGER monitor_signals_no_delete")
        db.execute("DELETE FROM monitor_signals WHERE id=?",(s[4]["id"],))
        db.execute("INSERT INTO monitor_signals VALUES (?,?,?,?,?)",(identifier,s[3].bot_id,signal["config_hash"],signal["candle_time"],payload))
    with pytest.raises(DecisionError,match="SIGNAL_NOT_ELIGIBLE"):
        service.record_decision(binding["id"],identifier,proposal["validation_hash"])


def test_hold_recorded_without_trade_intent(services):
    s,service=services
    _,signal,wallet,binding=positioned_scenario(s,strategy="buy_hold")
    registered=service.register_binding(binding)
    service.activate_binding(registered["id"])
    proposed=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    before=tables(s[0])
    decision=service.record_decision(registered["id"],signal["id"],proposed["validation_hash"])
    assert decision["proposal"]["status"] == "HOLD" and decision["proposal"]["planned_quantity"] is None
    assert decision["proposal"]["execution_enabled"] is False and tables(s[0]) == before


def test_detect_tampered_binding_and_active_projection(services):
    s,service=services
    binding=active(s,service)
    with s[0].connect() as db:
        db.execute("DELETE FROM paper_binding_active WHERE binding_id=?",(binding["id"],))
    with pytest.raises(DecisionError,match="BINDING_PROJECTION_INTEGRITY_ERROR"):
        service.verify_integrity()


def test_binding_immutable_trigger_and_tamper_detection(services):
    s,service=services
    binding=service.register_binding(s[6])
    with pytest.raises(sqlite3.IntegrityError):
        with s[0].connect() as db: db.execute("UPDATE paper_bindings SET payload='{}'")
    with s[0].connect() as db:
        db.execute("DROP TRIGGER paper_bindings_no_update")
        db.execute("UPDATE paper_bindings SET payload='{}' WHERE id=?",(binding["id"],))
    with pytest.raises(DecisionError,match="BINDING_INTEGRITY_ERROR"):
        service.get_binding(binding["id"])


def test_concurrent_activations_one_winner(services):
    s,service=services
    one=service.register_binding(s[6]); s[6]["risk"]["risk_fraction"]="0.02"; two=service.register_binding(s[6])
    def attempt(identifier):
        try:
            return DecisionService(s[0].path,clock=lambda:s[7][0]).activate_binding(identifier)["state"]
        except DecisionError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,[one["id"],two["id"]]))
    assert sorted(outcomes) == ["ACTIVE","BINDING_ACTIVE_CONFLICT"]


def test_incompatible_active_bot_configuration(services):
    s,service=services
    first=active(s,service)
    config=s[3].model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    other=MonitorRuntime(s[0],clock=lambda:s[7][0]).once(config)
    binding=dict(s[6]); binding["monitor_config_hash"]=other["config_hash"]
    candidate=service.register_binding(binding)
    with pytest.raises(DecisionError,match="BINDING_ACTIVE_CONFLICT"):
        service.activate_binding(candidate["id"])
    assert service.get_binding(first["id"])["state"] == "ACTIVE"


def test_other_active_monitor_configuration_blocks_activation(services):
    s,service=services
    binding=service.register_binding(s[6])
    config=s[3].model_copy(update={"parameters":StrategyParameters(fast=2,slow=4,trend_entry="state")})
    runtime=MonitorRuntime(s[0],clock=lambda:s[7][0])
    key,owner,_=runtime.claim(config)
    with pytest.raises(DecisionError,match="AMBIGUOUS_BOT_CONFIG"):
        service.activate_binding(binding["id"])
    runtime.release(key,owner)
    assert service.activate_binding(binding["id"])["state"] == "ACTIVE"


def test_cli_binding_decision_and_live_guard(services,tmp_path,monkeypatch,capsys):
    from cryptolab.paper.decision_cli import main
    s,_=services
    binding_file=tmp_path/"binding.json"; binding_file.write_text(json.dumps(s[6]),encoding="utf-8")
    monkeypatch.setenv("CRYPTOLAB_DATABASE",str(s[0].path))
    monkeypatch.setattr("cryptolab.paper.decisions.time.time",lambda:s[7][0]/1000)
    def command(*args):
        monkeypatch.setattr("sys.argv",["decisions",*args])
        rc=main(); return rc,json.loads(capsys.readouterr().out)
    before=tables(s[0])
    rc,binding=command("register-binding","--binding",str(binding_file)); assert rc == 0
    rc,activated=command("activate-binding","--id",binding["id"]); assert rc == 0 and activated["state"] == "ACTIVE"
    proposal=plan(s)
    rc,decision=command("record-decision","--binding-id",binding["id"],"--signal",s[4]["id"],"--validation-hash",proposal["validation_hash"])
    assert rc == 0 and decision["state"] == "RECORDED" and decision["receipt_mode"] == "REGISTER_NEW_DECISION"
    ticker=s[2].ticker.model_copy(update={"high_24h":s[2].ticker.high_24h+1})
    s[0].save(s[2].model_copy(update={"ticker":ticker}))
    rc,receipt=command("record-decision","--binding-id",binding["id"],"--signal",s[4]["id"],"--validation-hash",proposal["validation_hash"])
    assert rc == 0 and receipt["id"] == decision["id"] and receipt["receipt_mode"] == "RECOVER_EXISTING_RECEIPT"
    assert receipt["execution_enabled"] is False and receipt["needs_revalidation"] is True
    assert command("verify")[1]["valid"] and tables(s[0]) == before
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError): command("list-bindings")
