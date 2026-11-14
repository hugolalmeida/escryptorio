"""Dashboard paper: fixtures isoladas, sem escrita nas consultas."""
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.paper.models import FillRecord, StateRecord, WalletSpec
from cryptolab.paper.storage import PaperStore
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.executor_models import VirtualExecutionRequest
from cryptolab.paper.marking import PaperMarker
from cryptolab.config import Settings
from test_paper_decisions import services, active, record
from test_paper_planner import setup_planner, positioned_scenario
from decimal import Decimal, localcontext
from cryptolab.paper.ledger import LEDGER_CONTEXT


TABLES = ("paper_wallets", "paper_events", "paper_heads", "paper_bindings", "paper_decisions",
          "paper_mark_evidence", "paper_execution_evidence", "paper_decision_clock")


def content(store):
    with store.connect() as db:
        return {t: [tuple(row) for row in db.execute("SELECT * FROM " + t)] for t in TABLES}


def test_empty_readonly_and_routes(settings, store):
    before = content(store)
    with TestClient(create_app(settings)) as client:
        result = client.get('/api/v1/paper/overview')
        assert result.status_code == 200 and result.json()['data']['summary']['wallets'] == 0
        assert client.get('/api/v1/paper/signals').json()['data'] == []
        assert client.get('/api/v1/paper/decisions').json()['data'] == []
        assert client.post('/api/v1/paper/overview').status_code == 405
        assert client.get('/api/v1/paper/wallets/invalid').status_code == 422
        assert client.get('/api/v1/paper/signals?limit=101').status_code == 422
    assert content(store) == before


def test_position_without_verified_mark_is_unavailable(settings, store):
    paper = PaperStore(store.path)
    wallet = paper.create_wallet(WalletSpec(bot_id='synthetic', strategy='trend', symbol='BTCUSDT', interval='60', initial_capital='1000', opened_at=0), 'create')
    wid = wallet['wallet_id']
    paper.append(wid, 'activate', StateRecord(state='active', event_time=1))
    paper.append(wid, 'legacy-fill', FillRecord(side='buy', quantity='1', price='100', fee='1', reference_price='100', candle_time=3600, event_time=3600))
    before = content(store)
    with TestClient(create_app(settings)) as client:
        result = client.get('/api/v1/paper/overview').json()['data']
        assert result['summary']['cash'] == '899' and result['summary']['equity'] is None
        assert result['wallets'][0]['average_cost'] == '101' and result['wallets'][0]['mark_status'] == 'UNAVAILABLE'
        fills = client.get(f'/api/v1/paper/wallets/{wid}/fills?limit=1').json()['data']
        assert fills['total'] == 1 and fills['items'][0]['provenance'] == 'LEGACY_UNVERIFIED'
    assert content(store) == before


def test_corrupt_checkpoint_fails_closed(settings, store):
    paper = PaperStore(store.path)
    wallet = paper.create_wallet(WalletSpec(bot_id='corrupt', strategy='trend', symbol='BTCUSDT', interval='60', initial_capital='1000', opened_at=0), 'create')
    with store.connect() as db:
        db.execute('UPDATE paper_heads SET event_hash=? WHERE wallet_id=?', ('0'*64, wallet['wallet_id']))
    before = content(store)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/paper/overview').status_code == 503
    assert content(store) == before


def test_verified_fill_and_expired_decision_are_read_only(services, monkeypatch):
    s, service = services
    binding = active(s, service)
    decision = record(s, service, binding)
    monkeypatch.setenv('PAPER_SIMULATION_ENABLED', 'true')
    result = PaperExecutor(s[0].path, clock=lambda: s[7][0]).execute(VirtualExecutionRequest(decision_id=decision['id'], idempotency_key='fixture-only'), paper=True)
    monkeypatch.setenv('PAPER_SIMULATION_ENABLED', 'false')
    monkeypatch.setattr('cryptolab.paper.api.time.time', lambda: decision['proposal']['expires_at'] + 1)
    before = content(s[0])
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        decisions = client.get('/api/v1/paper/decisions').json()['data']
        assert decisions[0]['state'] == 'RECORDED' and decisions[0]['temporal_status'] == 'EXPIRED'
        assert decisions[0]['execution_id'] == result['execution_id']
        fills = client.get(f"/api/v1/paper/wallets/{s[5]['wallet_id']}/fills").json()['data']
        assert fills['items'][0]['provenance'] == 'VERIFIED'
        assert fills['items'][0]['decision_id'] == decision['id']
    assert content(s[0]) == before


def test_partial_sell_realized_pnl_and_pagination(settings, store):
    paper = PaperStore(store.path)
    w = paper.create_wallet(WalletSpec(bot_id='partial', strategy='trend', symbol='BTCUSDT', interval='60', initial_capital='1000', opened_at=0), 'create')
    wid = w['wallet_id']
    paper.append(wid, 'activate', StateRecord(state='active', event_time=1))
    paper.append(wid, 'buy', FillRecord(side='buy', quantity='2', price='100', fee='2', reference_price='100', candle_time=3600, event_time=3600))
    paper.append(wid, 'sell', FillRecord(side='sell', quantity='1', price='120', fee='1', reference_price='120', candle_time=3600, event_time=3601))
    before = content(store)
    with TestClient(create_app(settings)) as client:
        w = client.get(f'/api/v1/paper/wallets/{wid}').json()['data']
        assert w['state']['cash'] == '917' and w['state']['quantity'] == '1'
        assert w['state']['acquisition_cost'] == '101' and w['state']['realized_pnl'] == '18'
        assert w['equity'] is None and w['unrealized_pnl'] is None
        p1 = client.get(f'/api/v1/paper/wallets/{wid}/fills?limit=1&offset=0').json()['data']
        p2 = client.get(f'/api/v1/paper/wallets/{wid}/fills?limit=1&offset=1').json()['data']
        assert p1['total'] == 2 and p1['items'][0]['event']['payload']['input']['side'] == 'sell'
        assert p2['items'][0]['event']['payload']['input']['side'] == 'buy'
    assert content(store) == before


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / 'missing.sqlite3'
    client = TestClient(create_app(Settings(database_path=path)))
    assert client.get('/api/v1/paper/overview').status_code == 503
    assert not path.exists()


def test_reserved_fill_without_evidence_blocks_overview(settings, store):
    paper = PaperStore(store.path)
    w = paper.create_wallet(WalletSpec(bot_id='orphan', strategy='trend', symbol='BTCUSDT', interval='60', initial_capital='1000', opened_at=0), 'create')
    paper.append(w['wallet_id'], 'activate', StateRecord(state='active', event_time=1))
    paper.append(w['wallet_id'], 'exec-' + 'a'*64, FillRecord(side='buy', quantity='1', price='100', fee='1', reference_price='100', candle_time=3600, event_time=3600))
    before = content(store)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/paper/overview').status_code == 503
    assert content(store) == before


def test_verified_fresh_mark_and_stale_aggregation(services, monkeypatch):
    s, service = services
    _, signal, wallet, binding = positioned_scenario(s, strategy="trend")
    registered = service.register_binding(binding)
    service.activate_binding(registered["id"])
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "true")
    marker = PaperMarker(s[0].path, clock=lambda: s[7][0])
    mark = marker.mark(registered["id"], signal["id"], "fresh-test")
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    other = s[1].create_wallet(WalletSpec(bot_id="second", strategy="trend", symbol="ETHUSDT", interval="60", initial_capital="500", opened_at=0), "second")
    before = content(s[0])
    monkeypatch.setattr("cryptolab.paper.api.time.time", lambda: s[7][0] / 1000)
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        data = client.get("/api/v1/paper/overview").json()["data"]
        w = next(x for x in data["wallets"] if x["wallet_id"] == wallet["wallet_id"])
        with localcontext(LEDGER_CONTEXT):
            qty, price = Decimal(w["state"]["quantity"]), Decimal(mark["price"])
            cost, cash = Decimal(w["state"]["acquisition_cost"]), Decimal(w["state"]["cash"])
            realized = Decimal(w["state"]["realized_pnl"])
            value = qty * price
            assert w["mark_status"] == "FRESH"
            assert Decimal(w["position_value"]) == value
            assert Decimal(w["equity"]) == cash + value
            assert Decimal(w["unrealized_pnl"]) == value - cost
            assert Decimal(w["total_pnl"]) == realized + value - cost
            assert Decimal(w["average_cost"]) == cost / qty
            assert Decimal(w["exposure"]) == value / (cash + value)
            # The acquisition cost already incorporates entry fees.
            assert Decimal(data["summary"]["equity"]) == sum(Decimal(x["equity"]) for x in data["wallets"])
        s[7][0] += 91000
        stale = client.get("/api/v1/paper/overview").json()["data"]
        w = next(x for x in stale["wallets"] if x["wallet_id"] == wallet["wallet_id"])
        assert w["mark_status"] == "STALE" and w["equity"] is None and w["unrealized_pnl"] is None and w["total_pnl"] is None
        assert stale["summary"]["equity"] is None and stale["summary"]["unrealized_pnl"] is None
        no_position = next(x for x in stale["wallets"] if x["wallet_id"] == other["wallet_id"])
        assert Decimal(no_position["unrealized_pnl"]) == 0 and Decimal(no_position["equity"]) == 500
    assert content(s[0]) == before


def test_mark_before_last_fill_cannot_price_position(services, monkeypatch):
    s, service = services
    binding = active(s, service)
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "true")
    PaperMarker(s[0].path, clock=lambda: s[7][0]).mark(binding["id"], s[4]["id"], "before-fill")
    s[1].append(s[5]["wallet_id"], "synthetic-buy-after-mark", FillRecord(side="buy", quantity="1", price="100", fee="1", reference_price="100", candle_time=s[4]["decision_time"], event_time=s[7][0]//1000))
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setattr("cryptolab.paper.api.time.time", lambda: s[7][0]/1000)
    before = content(s[0])
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        w = client.get(f"/api/v1/paper/wallets/{s[5]['wallet_id']}").json()["data"]
        assert w["mark_status"] == "STALE"
        assert w["equity"] is None and w["unrealized_pnl"] is None and w["total_pnl"] is None
    assert content(s[0]) == before


def test_tampered_mark_evidence_blocks_read(services, monkeypatch):
    s, service = services
    _, signal, wallet, binding = positioned_scenario(s, strategy="trend")
    registered = service.register_binding(binding); service.activate_binding(registered["id"])
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "true")
    mark = PaperMarker(s[0].path, clock=lambda: s[7][0]).mark(registered["id"], signal["id"], "tamper-dashboard")
    with s[0].connect() as db:
        db.execute("DROP TRIGGER paper_mark_evidence_no_update")
        db.execute("UPDATE paper_mark_evidence SET payload='{}' WHERE id=?", (mark["id"],))
    before = content(s[0])
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        assert client.get("/api/v1/paper/overview").status_code == 503
    assert content(s[0]) == before


def test_fresh_mark_fee_in_cost_not_subtracted_twice(services, monkeypatch):
    s, service = services
    binding = active(s, service)
    s[1].append(s[5]["wallet_id"], "synthetic-buy-fee", FillRecord(side="buy", quantity="1", price="100", fee="2", reference_price="100", candle_time=s[4]["decision_time"], event_time=s[7][0]//1000))
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "true")
    mark = PaperMarker(s[0].path, clock=lambda: s[7][0]).mark(binding["id"], s[4]["id"], "fresh-with-fee")
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setattr("cryptolab.paper.api.time.time", lambda: s[7][0]/1000)
    before = content(s[0])
    with TestClient(create_app(Settings(database_path=s[0].path))) as client:
        w = client.get(f"/api/v1/paper/wallets/{s[5]['wallet_id']}").json()["data"]
        assert Decimal(w["state"]["acquisition_cost"]) == Decimal("102")
        assert Decimal(w["state"]["total_fees"]) == Decimal("2")
        assert Decimal(w["unrealized_pnl"]) == Decimal(mark["price"]) - Decimal("102")
        assert Decimal(w["equity"]) == Decimal("898") + Decimal(mark["price"])
    assert content(s[0]) == before
