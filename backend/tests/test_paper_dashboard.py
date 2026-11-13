"""Dashboard paper: fixtures isoladas, sem escrita nas consultas."""
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.paper.models import FillRecord, StateRecord, WalletSpec
from cryptolab.paper.storage import PaperStore
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.executor_models import VirtualExecutionRequest
from cryptolab.config import Settings
from test_paper_decisions import services, active, record
from test_paper_planner import setup_planner


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
