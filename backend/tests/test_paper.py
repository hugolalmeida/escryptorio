"""Fixtures sintéticas isoladas; não representam preços reais nem execução automática."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D, localcontext

import pytest

from cryptolab.paper.cli import main
from cryptolab.paper.models import FillRecord, MarkRecord, StateRecord, WalletSpec
from cryptolab.paper.storage import PaperError, PaperStore, _event
from cryptolab.history.models import canonical_json


@pytest.fixture
def paper(settings):
    store = PaperStore(settings.database_path)
    store.migrate()
    return store


def wallet(store, bot="bot_1", key="create-1", capital="1000"):
    return store.create_wallet(WalletSpec(bot_id=bot,strategy="trend",symbol="BTCUSDT",interval="60",
        initial_capital=capital,opened_at=0), key)


def active(store, wallet_id):
    return store.append(wallet_id,"state-active",StateRecord(state="active",event_time=3600))


def fill(side="buy", quantity="2", price="100", fee="1", event_time=7200):
    return FillRecord(side=side,quantity=quantity,price=price,fee=fee,reference_price="100",
        candle_time=7200,event_time=event_time)


def test_rebuild_balances_fees_pnl_marks_and_exact_audit(paper):
    w = wallet(paper)
    assert w["state"]["cash"] == "1000" and w["state"]["state"] == "paused"
    assert w["ledger_version"] == "cryptolab-paper-ledger/1"
    assert w["state"]["equity"] == "1000" and w["sequence"] == 1
    active(paper,w["wallet_id"])
    buy = paper.append(w["wallet_id"],"fill-1",fill())
    assert buy["payload"]["before"]["cash"] == "1000"
    assert buy["payload"]["after"]["cash"] == "799"
    assert buy["payload"]["after"]["equity"] is None
    paper.append(w["wallet_id"],"mark-1",MarkRecord(price="110",candle_time=7200,event_time=7200))
    sell = paper.append(w["wallet_id"],"fill-2",fill("sell","1","120","1"))
    assert sell["payload"]["after"]["cash"] == "918"
    assert sell["payload"]["after"]["acquisition_cost"] == "100.5"
    assert sell["payload"]["after"]["realized_pnl"] == "18.5"
    assert sell["payload"]["after"]["equity"] == "1028"
    paper.append(w["wallet_id"],"fill-3",fill("sell","1","100","1"))
    restored = PaperStore(paper.path).wallet(w["wallet_id"])
    assert restored["state"]["cash"] == "1017"
    assert restored["state"]["quantity"] == "0"
    assert restored["state"]["acquisition_cost"] == "0"
    assert restored["state"]["realized_pnl"] == "17"
    assert restored["state"]["total_fees"] == "3"
    assert restored["state"]["equity"] == "1017"
    assert restored["sequence"] == 6
    events = paper.events(w["wallet_id"])
    assert [e["sequence"] for e in events] == list(range(1,7))
    assert all(b["previous_hash"] == a["event_hash"] for a,b in zip(events,events[1:]))
    assert events[2]["payload"]["input"]["reference_price"] == "100"
    assert events[2]["payload"]["input"]["candle_time"] == 7200


def test_independent_wallets_idempotency_and_conflicting_retries(paper):
    a = wallet(paper)
    assert wallet(paper) == a
    b = wallet(paper,"bot_2","create-2","500")
    with pytest.raises(PaperError, match="BOT_ALREADY_EXISTS"): wallet(paper,"bot_1","create-3")
    with pytest.raises(PaperError, match="IDEMPOTENCY_CONFLICT"): wallet(paper,"bot_3","create-1")
    for w in (a,b): active(paper,w["wallet_id"])
    first = paper.append(a["wallet_id"],"fill-same",fill())
    same = fill(quantity="2.0",price="100.00",fee="1.000")
    assert paper.append(a["wallet_id"],"fill-same",same) == first
    with pytest.raises(PaperError, match="IDEMPOTENCY_CONFLICT"):
        paper.append(a["wallet_id"],"fill-same",fill(quantity="1"))
    paper.append(b["wallet_id"],"fill-same",fill(quantity="1"))
    assert paper.wallet(a["wallet_id"])["state"]["cash"] == "799"
    assert paper.wallet(b["wallet_id"])["state"]["cash"] == "399"
    assert len(paper.wallets()) == 2


def test_prohibit_short_margin_pause_bad_reference_and_nonfinite(paper):
    w=wallet(paper,capital="100")
    with pytest.raises(ValueError, match="pausada"): paper.append(w["wallet_id"],"paused-fill",fill())
    active(paper,w["wallet_id"])
    with pytest.raises(ValueError, match="Saldo insuficiente"): paper.append(w["wallet_id"],"no-margin",fill())
    with pytest.raises(ValueError, match="short proibido"): paper.append(w["wallet_id"],"no-short",fill("sell"))
    with pytest.raises(ValueError, match="candle"): paper.append(w["wallet_id"],"bad-candle",fill().model_copy(update={"candle_time":7201}))
    with pytest.raises(ValueError): FillRecord(side="buy",quantity="NaN",price="100",fee="0",reference_price="100",candle_time=7200,event_time=7200)
    with pytest.raises(ValueError,match="float"):
        FillRecord(side="buy",quantity=0.1,price="100",fee="0",reference_price="100",candle_time=7200,event_time=7200)
    with pytest.raises(ValueError): wallet(paper,"bad","create-bad",capital="Infinity")
    assert paper.wallet(w["wallet_id"])["sequence"] == 2
    assert paper.wallet(w["wallet_id"])["state"]["cash"] == "100"


def test_pausing_time_order_mark_history_and_sell_fee(paper):
    w=wallet(paper)
    wid=w["wallet_id"]
    active(paper,wid)
    paper.append(wid,"buy",fill())
    paper.append(wid,"mark-later",MarkRecord(price="120",candle_time=10800,event_time=10800))
    with pytest.raises(ValueError,match="ordem temporal"):
        paper.append(wid,"old-event",StateRecord(state="paused",event_time=7200))
    with pytest.raises(ValueError,match="regredir"):
        paper.append(wid,"old-mark",MarkRecord(price="110",candle_time=7200,event_time=10800))
    with pytest.raises(ValueError,match="Taxa superior"):
        paper.append(wid,"too-much-fee",fill("sell","1","100","101",event_time=10800))
    paper.append(wid,"pause",StateRecord(state="paused",event_time=10800))
    with pytest.raises(ValueError,match="pausada"):
        paper.append(wid,"paused-sell",fill("sell","1","100","0",event_time=10800))
    assert paper.wallet(wid)["state"]["mark_candle_time"] == 10800
    assert paper.wallet(wid)["state"]["equity"] == "1039"


def test_wallet_and_events_are_append_only_at_sql_level(paper):
    w=wallet(paper)
    for statement in ("UPDATE paper_wallets SET bot_id='other'", "DELETE FROM paper_wallets",
                      "UPDATE paper_events SET payload='{}'", "DELETE FROM paper_events", "DELETE FROM paper_heads"):
        with pytest.raises(sqlite3.IntegrityError):
            with paper.connect() as db: db.execute(statement)
    assert paper.wallet(w["wallet_id"])["sequence"] == 1


def test_decimal_context_independence_and_partial_cost_basis(paper):
    w=wallet(paper,capital="1000.123456789012345678")
    active(paper,w["wallet_id"])
    r=fill(quantity="0.123456789012345678",price="123.123456789012345678",fee="0.000000000000000001")
    with localcontext() as ctx:
        ctx.prec=6
        event=paper.append(w["wallet_id"],"precise",r)
        view=paper.wallet(w["wallet_id"])
    with localcontext() as ctx:
        ctx.prec=80
        expected=D("1000.123456789012345678")-D("0.123456789012345678")*D("123.123456789012345678")-D("0.000000000000000001")
    assert D(view["state"]["cash"]) == expected
    assert event["payload"]["after"]["cash"] == view["state"]["cash"]
    paper.append(w["wallet_id"],"part",fill("sell","0.1","200","0"))
    assert D(paper.wallet(w["wallet_id"])["state"]["acquisition_cost"]) > 0


def test_partial_sale_ignores_caller_rounding_mode(paper):
    from decimal import ROUND_DOWN, ROUND_UP
    left=wallet(paper,"round-a","create-a")
    right=wallet(paper,"round-b","create-b")
    for w in (left,right):
        active(paper,w["wallet_id"])
        paper.append(w["wallet_id"],"buy",fill(quantity="3",price="100",fee="1"))
    with localcontext() as ctx:
        ctx.prec=6
        ctx.rounding=ROUND_DOWN
        paper.append(left["wallet_id"],"sell",fill("sell","1","110","0"))
    with localcontext() as ctx:
        ctx.prec=6
        ctx.rounding=ROUND_UP
        paper.append(right["wallet_id"],"sell",fill("sell","1","110","0"))
    assert paper.wallet(left["wallet_id"])["state"] == paper.wallet(right["wallet_id"])["state"]


def test_concurrent_idempotency_and_balance_atomicity(paper):
    w=wallet(paper,capital="100")
    active(paper,w["wallet_id"])
    def same(_):
        return PaperStore(paper.path).append(w["wallet_id"],"same",fill(quantity="0.4",fee="0"))["event_id"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert len(set(pool.map(same,range(6)))) == 1
    def competing(i):
        try:
            PaperStore(paper.path).append(w["wallet_id"],f"other-{i}",fill(quantity="0.4",fee="0"))
            return "accepted"
        except ValueError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(competing,range(4)))
    assert results.count("accepted") == 1
    assert paper.wallet(w["wallet_id"])["state"]["cash"] == "20"
    assert paper.wallet(w["wallet_id"])["sequence"] == 4


def test_failed_checkpoint_rolls_back_event_and_retry_succeeds(paper):
    w=wallet(paper)
    active(paper,w["wallet_id"])
    with paper.connect() as db:
        db.execute("CREATE TRIGGER paper_test_fail BEFORE UPDATE ON paper_heads BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError): paper.append(w["wallet_id"],"retry",fill())
    assert paper.wallet(w["wallet_id"])["sequence"] == 2
    with paper.connect() as db: db.execute("DROP TRIGGER paper_test_fail")
    event=PaperStore(paper.path).append(w["wallet_id"],"retry",fill())
    assert event["sequence"] == 3
    assert paper.append(w["wallet_id"],"retry",fill()) == event


@pytest.mark.parametrize("tamper",["event", "truncate", "head", "wallet"])
def test_detect_tampering_in_events_checkpoint_and_metadata(paper,tamper):
    w=wallet(paper)
    active(paper,w["wallet_id"])
    paper.append(w["wallet_id"],"buy",fill())
    with paper.connect() as db:
        if tamper == "event":
            db.execute("DROP TRIGGER paper_events_no_update")
            db.execute("UPDATE paper_events SET payload='{}' WHERE sequence=2")
        elif tamper == "truncate":
            db.execute("DROP TRIGGER paper_events_no_delete")
            db.execute("DELETE FROM paper_events WHERE sequence=3")
        elif tamper == "head":
            db.execute("UPDATE paper_heads SET event_hash=?",("0"*64,))
        else:
            db.execute("DROP TRIGGER paper_wallets_no_update")
            db.execute("UPDATE paper_wallets SET bot_id='forged'")
    with pytest.raises(PaperError, match="LEDGER_INTEGRITY_ERROR"): paper.wallet(w["wallet_id"])
    with pytest.raises(PaperError, match="LEDGER_INTEGRITY_ERROR"): paper.append(w["wallet_id"],"next",fill())


def test_rehashed_false_balance_is_rejected(paper):
    w=wallet(paper)
    active(paper,w["wallet_id"])
    record=paper.append(w["wallet_id"],"buy",fill())
    payload=record["payload"]
    payload["after"]["cash"]="99999"
    forged=_event(w["wallet_id"],record["sequence"],"buy","fill",payload,record["previous_hash"])
    with paper.connect() as db:
        db.execute("DROP TRIGGER paper_events_no_update")
        db.execute("UPDATE paper_events SET payload=?,event_hash=? WHERE event_id=?",(canonical_json(payload),forged["event_hash"],record["event_id"]))
        db.execute("UPDATE paper_heads SET event_hash=? WHERE wallet_id=?",(forged["event_hash"],w["wallet_id"]))
    with pytest.raises(PaperError, match="LEDGER_INTEGRITY_ERROR"): paper.wallet(w["wallet_id"])


def test_cli_create_show_ledger_verify_and_live_guard(settings,monkeypatch,capsys):
    monkeypatch.setenv("CRYPTOLAB_DATABASE",str(settings.database_path))
    monkeypatch.setattr("sys.argv",["paper","create","--bot","cli-bot","--strategy","rsi","--symbol","ETHUSDT",
        "--interval","60","--capital","1000","--opened-at","3600","--key","cli-create"])
    assert main() == 0
    created=json.loads(capsys.readouterr().out)
    for command in ("show","ledger","verify"):
        monkeypatch.setattr("sys.argv",["paper",command,"--wallet",created["wallet_id"]])
        assert main() == 0
        output=json.loads(capsys.readouterr().out)
        if command == "verify": assert output["valid"] and output["sequence"] == 1
        if command == "ledger": assert output[0]["kind"] == "genesis"
    monkeypatch.setenv("LIVE_TRADING_ENABLED","true")
    with pytest.raises(RuntimeError,match="Execução real indisponível"): main()
