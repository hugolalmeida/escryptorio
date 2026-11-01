import time
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from cryptolab.config import INTERVALS
from cryptolab.models import Candle
from cryptolab.history.models import HistoryRequest, utc_iso
from cryptolab.history.source import HistoryTransportError
from cryptolab.history.storage import HistoryError, HistoryStore, job_request


class PageSource(Protocol):
    def page(self, request: HistoryRequest) -> dict: ...


@dataclass(frozen=True)
class HistoricalPage:
    candles: list[Candle]
    source_time_ms: int
    received_count: int
    duplicate_count: int
    open_count: int
    outside_count: int


def normalize_page(response: dict, request: HistoryRequest) -> HistoricalPage:
    try:
        result = response["result"]
        if response["retCode"] != 0 or result["category"] != "spot" or result["symbol"] != request.symbol:
            raise ValueError("wrong market")
        rows, source = result["list"], int(response["time"])
        if not isinstance(rows, list) or len(rows) > 1000 or source <= 0:
            raise ValueError("invalid envelope")
        if source > int(time.time()*1000)+5000:
            raise HistoryError("BYBIT_CLOCK_SKEW")
        step = INTERVALS[request.interval]
        unique, duplicates, opened, outside = {}, 0, 0, 0
        for row in rows:
            if not isinstance(row, list) or len(row) != 7 or not all(isinstance(v, str) for v in row):
                raise ValueError("invalid row")
            stamp = int(row[0])
            if stamp % 1000 or stamp//1000 % step:
                raise ValueError("unaligned timestamp")
            candle = Candle(time=stamp//1000, open=row[1], high=row[2], low=row[3], close=row[4],
                            volume=row[5], turnover=row[6], closed=stamp+step*1000 <= source)
            # Validate duplicates before range/closed filtering, without rounding Decimals.
            if candle.time in unique:
                if candle != unique[candle.time]:
                    raise HistoryError("CANDLE_CONFLICT")
                duplicates += 1
            else:
                unique[candle.time] = candle
        candles = []
        for candle in sorted(unique.values(), key=lambda c: c.time):
            if not request.start_time <= candle.time < request.end_time:
                outside += 1
            elif not candle.closed:
                opened += 1
            else:
                candles.append(candle)
        return HistoricalPage(candles, source, len(rows), duplicates, opened, outside)
    except HistoryError:
        raise
    except (KeyError, IndexError, ValueError, TypeError, OverflowError):
        raise HistoryError("BYBIT_INVALID_HISTORICAL_PAGE") from None


class HistoricalCollector:
    def __init__(self, store: HistoryStore, source: PageSource, *, page_size: int = 1000,
                 sleep: Callable[[float], None] = time.sleep, on_progress: Callable[[dict], None] | None = None):
        if not 1 <= page_size <= 1000:
            raise ValueError("Página deve conter entre 1 e 1000 candles")
        self.store, self.source, self.page_size = store, source, page_size
        self.sleep, self.on_progress = sleep, on_progress
        self.owner = uuid.uuid4().hex

    def check_pause(self):
        if self.store.heartbeat(self.owner):
            raise HistoryError("PAUSE_REQUESTED")

    def wait(self, seconds: float):
        # Esperas curtas tornam pausa/cancelamento responsivos e renovam o lease.
        while seconds > 0:
            self.check_pause()
            portion = min(seconds, 1)
            self.sleep(portion)
            seconds -= portion

    def fetch(self, request: HistoryRequest) -> dict:
        for attempt in range(4):
            self.check_pause()
            # Até duas chamadas por segundo, além de backoff e resets informados pela API.
            self.wait(.5)
            try:
                return self.source.page(request)
            except HistoryTransportError as exc:
                if not exc.retryable or attempt == 3:
                    raise
                self.wait(max(2**(attempt+1), exc.retry_after))
        raise HistoryError("RETRY_EXHAUSTED")

    def run(self, job_id: str | None = None) -> dict | None:
        claimed = self.store.claim(self.owner, job_id)
        if claimed is None:
            return None
        job, run_id = claimed
        request, dataset_id = job_request(job), None
        status, error = "failed", None
        try:
            coverage = self.store.coverage(request)
            # Planejamento finito por execução. Lacunas retornadas vazias não geram loops infinitos.
            for gap in coverage["gaps"]:
                cursor = gap["start_time"]
                while cursor < gap["end_time"]:
                    self.check_pause()
                    end = min(cursor+self.page_size*INTERVALS[request.interval], gap["end_time"])
                    window = HistoryRequest(symbol=request.symbol, interval=request.interval,
                                            start=utc_iso(cursor), end=utc_iso(end))
                    response = self.fetch(window)
                    page = normalize_page(response, window)
                    self.check_pause()
                    self.store.save_page(self.owner, run_id, window, page)
                    if self.on_progress:
                        self.on_progress(self.store.job(job["id"]))
                    self.wait(response.get("_next_delay", 0))
                    cursor = end
            self.check_pause()
            if self.store.coverage(request)["complete"]:
                dataset_id = self.store.approve(self.owner, job)
                status = "completed"
            else:
                status, error = "incomplete", "MISSING_CANDLES"
        except KeyboardInterrupt:
            status, error = "paused", "INTERRUPTED"
        except HistoryError as exc:
            if str(exc) == "LEASE_LOST":
                return self.store.job(job["id"])
            status = "paused" if str(exc) == "PAUSE_REQUESTED" else "failed"
            error = str(exc)
        except Exception:
            # A transação de página já fez rollback. Não expor detalhes de SDK/banco em logs/API.
            status, error = "failed", "HISTORY_INTERNAL_ERROR"
        try:
            self.store.finish(self.owner, run_id, job["id"], status, error, dataset_id)
        except HistoryError as exc:
            if str(exc) != "LEASE_LOST":
                raise
        return self.store.job(job["id"])
