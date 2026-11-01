import hashlib
import json
import sqlite3
from decimal import Decimal as D, getcontext

import pytest
from fastapi.testclient import TestClient

from cryptolab.api import create_app
from cryptolab.history.collector import HistoricalCollector, normalize_page
from cryptolab.history.models import HistoryRequest, candle_payload, canonical_history, parse_utc, utc_iso
from cryptolab.history.reader import DatasetReader
from cryptolab.history.source import HistoricalBybit, HistoryTransportError, retry_delay
from cryptolab.history.storage import HistoryError, HistoryStore
from cryptolab.config import INTERVALS

START = parse_utc("2024-01-01")


def request_for(size=2501, interval="60", start=START):
    return HistoryRequest(symbol="BTCUSDT", interval=interval, start=utc_iso(start),
                          end=utc_iso(start+size*INTERVALS[interval]))


class SyntheticSource:
    """Fixtures sintéticas exclusivamente de teste. Nenhuma rede ou dado de produção."""
    def __init__(self, gap=None, duplicate=False, fail_at=None, interrupt_at=None, source_time=None):
        self.calls, self.gap, self.duplicate = [], gap, duplicate
        self.fail_at, self.interrupt_at, self.source_time = fail_at, interrupt_at, source_time

    def page(self, request):
        self.calls.append(request)
        if self.interrupt_at == len(self.calls):
            raise KeyboardInterrupt()
        if self.fail_at is not None and len(self.calls) >= self.fail_at:
            raise HistoryTransportError("BYBIT_UNAVAILABLE", retryable=True)
        rows = [[str(t*1000), "100.000000000000000000000001", "103.10", "99.100", "102.01", "1.000000000000000000000009", "102.000"]
                for t in range(request.start_time, request.end_time, INTERVALS[request.interval]) if t != self.gap]
        if self.duplicate and rows:
            rows.append(rows[0].copy())
        return {"retCode": 0, "time": self.source_time or (request.end_time+3600)*1000,
                "result": {"category": "spot", "symbol": request.symbol, "list": list(reversed(rows))}}


@pytest.fixture
def history(settings):
    store = HistoryStore(settings.database_path)
    store.migrate()
    return store


def run_job(store, request=None, source=None, page_size=1000):
    job = store.enqueue(request or request_for())
    source = source or SyntheticSource()
    collector = HistoricalCollector(store, source, sleep=lambda _: None, page_size=page_size)
    return collector.run(job["id"]), source


def test_pagination_more_than_300_and_read_offline(history):
    request = request_for()
    job, source = run_job(history, request)
    assert job["status"] == "completed"
    assert job["stored_count"] == 2501
    assert job["pages"] == 3
    assert [r.expected_count for r in source.calls] == [1000, 1000, 501]
    assert all(a.end_time == b.start_time for a, b in zip(source.calls, source.calls[1:]))
    data = DatasetReader(history).read(job["dataset_id"])
    assert len(data.candles) == 2501
    assert data.candles[0].time == START
    assert data.candles[-1].time == request.end_time-3600
    assert data.candles[0].open == D("100.000000000000000000000001")
    assert data.candles[0].volume == D("1.000000000000000000000009")
    assert all(c.closed for c in data.candles)
    assert data.manifest["integrity_status"] == "approved"
    assert data.manifest["gaps"] == []
    assert len(source.calls) == 3  # leitura não chama a origem


@pytest.mark.parametrize("interval", ["15", "60", "240", "D"])
def test_timeframes_and_ordering(history, interval):
    request = request_for(37, interval)
    job, _ = run_job(history, request, page_size=13)
    data = DatasetReader(history).read(job["dataset_id"])
    assert [c.time for c in data.candles] == list(range(request.start_time, request.end_time, INTERVALS[interval]))


def test_duplicate_candles_are_deduplicated_and_recorded(history):
    job, source = run_job(history, request_for(15), SyntheticSource(duplicate=True))
    assert job["stored_count"] == 15
    assert job["status"] == "completed"
    with history.connect() as db:
        assert db.execute("SELECT duplicate_count FROM historical_pages").fetchone()[0] == 1


def test_conflicting_duplicate_rejects_page(history):
    class ConflictSource(SyntheticSource):
        def page(self, request):
            response = super().page(request)
            response["result"]["list"].append(response["result"]["list"][0].copy())
            response["result"]["list"][-1][4] = "101"
            return response
    job, _ = run_job(history, request_for(4), ConflictSource())
    assert job["status"] == "failed" and job["error_code"] == "CANDLE_CONFLICT"
    assert job["stored_count"] == 0


def test_missing_candles_recorded_never_fabricated_and_resume_only_gap(history):
    request = request_for(25)
    missing = START+8*3600
    job, source = run_job(history, request, SyntheticSource(gap=missing), page_size=10)
    assert job["status"] == "incomplete"
    assert job["stored_count"] == 24
    assert job["dataset_id"] is None
    assert job["gaps"] == [{"start_time": missing, "end_time": missing+3600, "candle_count": 1}]
    assert history.datasets() == []
    complete, resumed = run_job(history, request)
    assert complete["status"] == "completed" and complete["id"] == job["id"]
    assert len(resumed.calls) == 1 and resumed.calls[0].start_time == missing
    assert resumed.calls[0].expected_count == 1


def test_empty_response_finishes_incomplete_without_loop(history):
    class Empty(SyntheticSource):
        def page(self, request):
            response = super().page(request)
            response["result"]["list"] = []
            return response
    job, source = run_job(history, request_for(12), Empty(), page_size=5)
    assert job["status"] == "incomplete" and job["stored_count"] == 0
    assert len(source.calls) == 3


def test_open_candles_excluded_and_cannot_approve(history):
    request = request_for(20)
    source = SyntheticSource(source_time=(request.end_time-1800)*1000)
    job, _ = run_job(history, request, source)
    assert job["stored_count"] == 19
    assert job["status"] == "incomplete" and job["dataset_id"] is None
    with history.connect() as db:
        assert db.execute("SELECT open_count FROM historical_pages").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["unaligned", "negative_volume", "bad_high", "nan", "future_timestamp"])
def test_bad_page_rejected_before_persistence(history, change):
    class BadSource(SyntheticSource):
        def page(self, request):
            response = super().page(request)
            row = response["result"]["list"][0]
            if change == "unaligned": row[0] = str(int(row[0])+1)
            elif change == "negative_volume": row[5] = "-1"
            elif change == "bad_high": row[2] = "98"
            elif change == "nan": row[4] = "NaN"
            else: row[0] = "-1"
            return response
    job, _ = run_job(history, request_for(5), BadSource())
    assert job["status"] == "failed" and job["stored_count"] == 0
    assert job["error_code"] == "BYBIT_INVALID_HISTORICAL_PAGE"


def test_retry_backoff_bounded_and_preserves_progress(history):
    request = request_for(30)
    source = SyntheticSource(fail_at=2)
    sleeps = []
    job = history.enqueue(request)
    result = HistoricalCollector(history, source, page_size=10, sleep=sleeps.append).run(job["id"])
    assert result["status"] == "failed" and result["stored_count"] == 10
    assert len(source.calls) == 5  # primeira página + quatro tentativas na segunda
    assert sum(sleeps) == 16.5  # pacing 5*.5 + backoff 2+4+8
    resumed, next_source = run_job(history, request, page_size=10)
    assert resumed["status"] == "completed"
    assert len(next_source.calls) == 2 and next_source.calls[0].start_time == START+10*3600


def test_keyboard_interrupt_and_idempotent_resume(history):
    request = request_for(31)
    job, _ = run_job(history, request, SyntheticSource(interrupt_at=2), page_size=10)
    assert job["status"] == "paused" and job["stored_count"] == 10
    completed, resumed = run_job(history, request, page_size=10)
    assert completed["status"] == "completed" and len(resumed.calls) == 3
    before = history.job(job["id"])
    assert history.enqueue(request)["status"] == "completed"
    assert HistoricalCollector(history, resumed, sleep=lambda _: None).run(job["id"]) is None
    assert history.job(job["id"])["pages"] == before["pages"]
    assert len(history.datasets()) == 1


def test_overlapping_ranges_only_download_missing(history):
    run_job(history, request_for(10))
    job, source = run_job(history, request_for(20))
    assert len(source.calls) == 1 and source.calls[0].start_time == START+10*3600
    assert job["stored_count"] == 20


def test_hash_normalizes_decimals_not_collection_time_or_context(history):
    request = request_for(3)
    job, _ = run_job(history, request)
    candles = history.candles(request)
    expected = canonical_history(request, candles)
    changed = [c.model_copy(update={"volume": D("1.0000000000000000000000090")}) for c in candles]
    previous = getcontext().prec
    try:
        getcontext().prec = 6
        assert canonical_history(request, changed) == expected
    finally:
        getcontext().prec = previous
    assert "collected" not in expected[1] and "approved" not in expected[1]
    assert hashlib.sha256(expected[1].encode()).hexdigest() == job["dataset_id"]
    different = candles.copy()
    different[0] = different[0].model_copy(update={"volume": D(2)})
    assert canonical_history(request, different)[0] != expected[0]


def test_immutable_approved_data_and_candles(history):
    job, _ = run_job(history, request_for(2))
    for sql in ("UPDATE historical_datasets SET payload='tampered'", "DELETE FROM historical_datasets",
                "UPDATE historical_candles SET payload='tampered'", "DELETE FROM historical_candles"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with history.connect() as db:
                db.execute(sql)
    assert len(DatasetReader(history).read(job["dataset_id"]).candles) == 2


def test_reader_rejects_tampering_and_invalid_slices(history):
    request = request_for(6)
    job, _ = run_job(history, request)
    reader = DatasetReader(history)
    sliced = reader.read(job["dataset_id"], START+3600, START+3*3600)
    assert len(sliced.candles) == 2 and sliced.reference_hash == job["dataset_id"]
    for start, end in ((START-3600, START+3600), (START+1, START+3600), (START, request.end_time+3600)):
        with pytest.raises(HistoryError, match="INVALID_DATASET_RANGE"):
            reader.read(job["dataset_id"], start, end)
    with pytest.raises(HistoryError, match="DATASET_NOT_FOUND"):
        reader.read("0"*64)
    # Simula adulteração externa no banco isolado de teste, além da proteção SQL.
    with history.connect() as db:
        db.execute("DROP TRIGGER historical_datasets_no_update")
        db.execute("UPDATE historical_datasets SET payload=payload || ' '")
    with pytest.raises(HistoryError, match="DATASET_HASH_MISMATCH"):
        reader.read(job["dataset_id"])


def test_global_lease_blocks_second_collector_and_recovers_crash(history, monkeypatch):
    request = request_for(2)
    job = history.enqueue(request)
    claimed = history.claim("first", job["id"])
    assert claimed is not None
    assert history.claim("second", job["id"]) is None
    with history.connect() as db:
        db.execute("UPDATE historical_lease SET until_ms=0")
    recovered = history.claim("second", job["id"])
    assert recovered is not None
    with pytest.raises(HistoryError, match="LEASE_LOST"):
        history.heartbeat("first")
    assert history.job(job["id"])["runs"][0]["status"] == "interrupted"


def test_pause_requested_between_pages(history):
    request = request_for(20)
    job = history.enqueue(request)
    def pause(current):
        history.request_pause(current["id"])
    result = HistoricalCollector(history, SyntheticSource(), page_size=10, sleep=lambda _: None,
                                 on_progress=pause).run(job["id"])
    assert result["status"] == "paused" and result["stored_count"] == 10
    assert history.enqueue(request)["status"] == "queued"


def test_no_snapshot_mutation_and_migration_from_phase1(history, snapshot, settings):
    history.save(snapshot)
    run_job(history, request_for(5))
    history.migrate()
    assert history.load("BTCUSDT", "60") == snapshot
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/v1/market").json()
        assert data["dataset_id"] == snapshot.dataset_id
        assert data["ticker"]["price"] == "180.001"


@pytest.mark.parametrize("start,end,interval", [
    ("2024-01-01T00:00:00", "2024-01-02", "60"),
    ("2024-01-01T00:01:00Z", "2024-01-02", "60"),
    ("2024-01-02", "2024-01-01", "60"),
    ("2024-01-01T01:00:00Z", "2024-01-02", "240"),
    ("2024-01-01T01:00:00Z", "2024-01-02", "D"),
    ("2024-01-01T00:00:00.001Z", "2024-01-02", "60"),
    ("2020-01-01", "2026-01-01", "15"),
])
def test_invalid_utc_requests(start, end, interval):
    with pytest.raises(ValueError):
        HistoryRequest(symbol="BTCUSDT", interval=interval, start=start, end=end)


def test_timezone_normalization():
    assert request_for(24).start_time == HistoryRequest(symbol="BTCUSDT", interval="60",
        start="2023-12-31T21:00:00-03:00", end="2024-01-01T21:00:00-03:00").start_time


def test_history_api_local_queue_only_and_catalog(history, settings):
    req = request_for(8)
    headers = {"x-cryptolab-research": "1"}
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/history/jobs", json=req.model_dump()).status_code == 403
        assert client.post("/api/v1/history/jobs", json=req.model_dump(), headers={**headers, "origin": "https://evil.invalid"}).status_code == 403
        response = client.post("/api/v1/history/jobs", json=req.model_dump(), headers=headers)
        assert response.status_code == 202
        job = response.json()
        assert job["status"] == "queued" and job["stored_count"] == 0
        assert client.post("/api/v1/history/jobs", json=req.model_dump(), headers=headers).json()["id"] == job["id"]
        assert client.get("/api/v1/history/coverage", params=req.model_dump()).json()["complete"] is False
        assert client.post(f"/api/v1/history/jobs/{job['id']}/pause", headers=headers).json()["status"] == "paused"
        assert client.post(f"/api/v1/history/jobs/{job['id']}/resume", headers=headers).json()["status"] == "queued"
        assert client.post(f"/api/v1/history/jobs/{job['id']}/trade", headers=headers).status_code == 422
        completed = HistoricalCollector(history, SyntheticSource(), sleep=lambda _: None).run(job["id"])
        catalog = client.get("/api/v1/history/datasets").json()["datasets"]
        assert len(catalog) == 1
        details = client.get(f"/api/v1/history/datasets/{completed['dataset_id']}?limit=3").json()
        assert len(details["candles"]) == 3 and details["total_count"] == 8
        assert client.get("/api/v1/history/jobs/unknown").status_code == 404
        assert client.post("/api/v1/orders", headers=headers).status_code == 404
        assert client.get("/health").json()["live_trading_enabled"] is False


def test_sdk_history_is_public_spot_bounded_and_no_hidden_retries(monkeypatch):
    captured = []
    class FakeHTTP:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 1
            assert kwargs["force_retry"] is False
            assert not {"api_key", "api_secret"} & kwargs.keys()
            assert kwargs["testnet"] is False
        def get_kline(self, **kwargs):
            captured.append(kwargs)
            request = request_for(2)
            return SyntheticSource().page(request), None, {}
    monkeypatch.setattr("cryptolab.history.source.HTTP", FakeHTTP)
    request = request_for(2)
    data = HistoricalBybit().page(request)
    assert normalize_page(data, request).received_count == 2
    assert captured == [{"category": "spot", "symbol": "BTCUSDT", "interval": "60",
                         "start": request.start_time*1000, "end": request.end_time*1000-1, "limit": 1000}]


def test_rate_limit_headers_and_bans(monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1000)
    assert retry_delay({"Retry-After": "7", "X-Bapi-Limit-Reset-Timestamp": "1003000"}) == 7
    with pytest.raises(HistoryTransportError, match="RATE_LIMIT_WAIT_TOO_LONG"):
        retry_delay({"Retry-After": "600"})


def test_conflict_rolls_back_entire_page_and_provenance(history):
    run_job(history, request_for(1, start=START+3600))
    request = request_for(3)
    job = history.enqueue(request)
    _, run_id = history.claim("atomic", job["id"])
    response = SyntheticSource().page(request)
    response["result"]["list"][1][4] = "101"  # divergência num candle previamente validado
    page = normalize_page(response, request)
    with pytest.raises(HistoryError, match="CANDLE_CONFLICT"):
        history.save_page("atomic", run_id, request, page)
    assert history.coverage(request)["stored_count"] == 1
    assert [c.time for c in history.candles(request)] == [START+3600]
    assert history.job(job["id"])["pages"] == 0


def test_reject_future_server_time_and_outside_rows_not_archived(history, monkeypatch):
    request = request_for(2)
    response = SyntheticSource().page(request)
    monkeypatch.setattr("time.time", lambda: START)
    with pytest.raises(HistoryError, match="BYBIT_CLOCK_SKEW"):
        normalize_page(response, request)
    monkeypatch.setattr("time.time", lambda: request.end_time+10000)
    outside = response["result"]["list"][0].copy()
    outside[0] = str((request.start_time-3600)*1000)
    response["result"]["list"].append(outside)
    page = normalize_page(response, request)
    assert page.outside_count == 1 and len(page.candles) == 2


@pytest.mark.parametrize("code,retryable,name", [(403, False, "BYBIT_FORBIDDEN"),
    (429, True, "BYBIT_CODE_429"), (10006, True, "BYBIT_CODE_10006"), (500, True, "BYBIT_CODE_500")])
def test_sdk_errors_are_sanitized_and_classified(monkeypatch, code, retryable, name):
    from pybit.exceptions import FailedRequestError
    class BrokenSDK:
        def __init__(self, **kwargs): pass
        def get_kline(self, **kwargs):
            raise FailedRequestError(request="synthetic-private-payload", message="synthetic", status_code=code,
                                     time="now", resp_headers={"Retry-After": "2"})
    monkeypatch.setattr("cryptolab.history.source.HTTP", BrokenSDK)
    with pytest.raises(HistoryTransportError) as captured:
        HistoricalBybit().page(request_for(1))
    assert str(captured.value) == name
    assert captured.value.retryable is retryable
    assert captured.value.retry_after == 2


def test_unrecoverable_errors_do_not_retry(history):
    class Forbidden(SyntheticSource):
        def page(self, request):
            self.calls.append(request)
            raise HistoryTransportError("BYBIT_FORBIDDEN")
    job, source = run_job(history, request_for(3), Forbidden())
    assert job["status"] == "failed" and len(source.calls) == 1
    assert job["error_code"] == "BYBIT_FORBIDDEN"


def test_incomplete_and_open_data_cannot_be_canonical(history):
    request = request_for(3)
    run_job(history, request)
    candles = history.candles(request)
    with pytest.raises(ValueError):
        canonical_history(request, candles[:-1])
    with pytest.raises(ValueError):
        canonical_history(request, [*candles[:-1], candles[-1].model_copy(update={"closed": False})])
