"""Etapa A: testes isolados de proveniência e controle, sem fills novos."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from cryptolab.paper.decisions import DecisionService
from cryptolab.paper.marking import ExecutionError, PaperMarker, preview_decision, verify_mark
from cryptolab.paper.models import StateRecord
from cryptolab.paper.planner import VirtualTradePlanner
from test_paper_decisions import services, active, record
from test_paper_planner import setup_planner, tables, positioned_scenario


@pytest.fixture(autouse=True)
def paper_enabled(monkeypatch):
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED","true")
    monkeypatch.setenv("LIVE_TRADING_ENABLED","false")


def marker(s):
    return PaperMarker(s[0].path,clock=lambda:s[7][0])


def test_mark_provenance_and_idempotence_no_fill(services):
    s,service=services
    binding=active(s,service)
    before=s[1].wallet(s[5]["wallet_id"])
    result=marker(s).mark(binding["id"],s[4]["id"],"mark-one")
    assert result["receipt_mode"] == "NEW_MARK" and result["price"] == str(s[2].ticker.price)
    assert result["ticker_source_time_ms"] == s[2].ticker.source_time_ms and result["snapshot_hash"]
    again=marker(s).mark(binding["id"],s[4]["id"],"mark-one")
    assert again["id"] == result["id"] and again["receipt_mode"] == "RECOVER_MARK"
    with pytest.raises(ExecutionError,match="MARK_SOURCE_ALREADY_USED"):
        marker(s).mark(binding["id"],s[4]["id"],"another-key")
    with pytest.raises(ExecutionError,match="MARK_IDEMPOTENCY_CONFLICT"):
        marker(s).mark(binding["id"],"0"*64,"mark-one")
    after=s[1].wallet(s[5]["wallet_id"])
    assert after["sequence"] == before["sequence"]+1
    assert (after["state"]["cash"],after["state"]["quantity"]) == (before["state"]["cash"],before["state"]["quantity"])
    assert all(e["kind"] != "fill" for e in s[1].events(s[5]["wallet_id"]))


def test_concurrent_instances_one_mark(services):
    s,service=services; binding=active(s,service)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:marker(s).mark(binding["id"],s[4]["id"],"concurrent"),range(4)))
    assert len({r["id"] for r in results}) == 1
    assert len([e for e in s[1].events(s[5]["wallet_id"]) if e["kind"] == "mark"]) == 1


def test_mark_stale_and_paper_guard(services,monkeypatch):
    s,service=services; binding=active(s,service)
    before=tables(s[0]); s[7][0]+=91000
    with pytest.raises(ExecutionError,match="STALE_SNAPSHOT"):
        marker(s).mark(binding["id"],s[4]["id"],"stale")
    assert tables(s[0]) == before
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED","false")
    with pytest.raises(ExecutionError,match="PAPER_SIMULATION_DISABLED"):
        marker(s).mark(binding["id"],s[4]["id"],"disabled")
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError): marker(s).mark(binding["id"],s[4]["id"],"live")


def test_mark_rejects_paused_wallet(services):
    s,service=services; binding=active(s,service)
    s[1].append(s[5]["wallet_id"],"pause-fixture",StateRecord(state="paused",event_time=2))
    before=tables(s[0])
    with pytest.raises(ExecutionError,match="WALLET_PAUSED"):
        marker(s).mark(binding["id"],s[4]["id"],"paused")
    assert tables(s[0]) == before


def test_mark_tampered_provenance_detected(services):
    s,service=services; binding=active(s,service)
    mark=marker(s).mark(binding["id"],s[4]["id"],"tamper")
    with pytest.raises(sqlite3.IntegrityError):
        with s[0].connect() as db: db.execute("UPDATE paper_mark_evidence SET payload='{}'")
    with s[0].connect() as db:
        db.execute("DROP TRIGGER paper_mark_evidence_no_update")
        db.execute("UPDATE paper_mark_evidence SET payload='{}' WHERE id=?",(mark["id"],))
    with s[0].connect() as db:
        with pytest.raises(ExecutionError,match="MARK_INTEGRITY_ERROR"):
            verify_mark(db,s[1],mark["id"])


def test_mark_evidence_failure_rolls_back_ledger(services):
    s,service=services; binding=active(s,service)
    before=tables(s[0])
    with s[0].connect() as db:
        db.execute("CREATE TRIGGER abort_mark_test BEFORE INSERT ON paper_mark_evidence BEGIN SELECT RAISE(ABORT,'simulated'); END")
    with pytest.raises(ExecutionError,match="PAPER_DATABASE_ERROR"):
        marker(s).mark(binding["id"],s[4]["id"],"mark-rollback")
    assert tables(s[0]) == before
    with s[0].connect() as db: db.execute("DROP TRIGGER abort_mark_test")
    assert marker(s).mark(binding["id"],s[4]["id"],"mark-rollback")["receipt_mode"] == "NEW_MARK"


def test_preview_no_fill_and_invalidated(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    before=tables(s[0])
    assert preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])["status"] == "ELIGIBLE_FOR_VIRTUAL_REVIEW"
    assert tables(s[0]) == before
    service.invalidate_decision(item["id"],"REVIEW")
    with pytest.raises(ExecutionError,match="DECISION_NOT_RECORDED"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_preview_expired_blocks_and_preserves_clock(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    s[7][0]=item["proposal"]["expires_at"]*1000
    with pytest.raises(ExecutionError,match="DECISION_EXPIRED"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])
    s[7][0]-=1
    with pytest.raises(ExecutionError,match="CLOCK_ROLLBACK"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_preview_corrupt_checkpoint(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    with s[0].connect() as db: db.execute("UPDATE paper_decision_heads SET event_hash=? WHERE decision_id=?",("0"*64,item["id"]))
    with pytest.raises(ExecutionError,match="CHECKPOINT_INTEGRITY_ERROR"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_hold_rejected(services):
    s,service=services
    _,signal,wallet,binding=positioned_scenario(s,strategy="buy_hold")
    registered=service.register_binding(binding); service.activate_binding(registered["id"])
    plan=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    item=service.record_decision(registered["id"],signal["id"],plan["validation_hash"])
    with pytest.raises(ExecutionError,match="HOLD_NOT_EXECUTABLE"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_position_requires_mark_provenance(services):
    s,service=services
    _,signal,wallet,binding=positioned_scenario(s,strategy="trend")
    registered=service.register_binding(binding); service.activate_binding(registered["id"])
    plan=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    item=service.record_decision(registered["id"],signal["id"],plan["validation_hash"])
    with pytest.raises(ExecutionError,match="VERIFIED_MARK_REQUIRED"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_position_price_divergence_blocks_preview(services):
    s,service=services
    _,signal,wallet,binding=positioned_scenario(s,strategy="trend")
    registered=service.register_binding(binding); service.activate_binding(registered["id"])
    marker(s).mark(registered["id"],signal["id"],"verified-position")
    plan=VirtualTradePlanner(s[0].path,clock=lambda:s[7][0]).plan(wallet["wallet_id"],signal["id"],binding)
    item=service.record_decision(registered["id"],signal["id"],plan["validation_hash"])
    snap=s[0].load("BTCUSDT","60")
    ticker=snap.ticker.model_copy(update={"price":snap.ticker.price+1})
    s[0].save(snap.model_copy(update={"ticker":ticker}))
    with pytest.raises(ExecutionError,match="WALLET_MARK_STALE_OR_UNVERIFIED"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])


def test_corrupt_binding_projection_blocks_preview(services):
    s,service=services; binding=active(s,service); item=record(s,service,binding)
    with s[0].connect() as db:
        db.execute("DELETE FROM paper_binding_active WHERE binding_id=?",(binding["id"],))
    with pytest.raises(ExecutionError,match="INTEGRITY_ERROR"):
        preview_decision(s[0].path,item["id"],clock=lambda:s[7][0])
