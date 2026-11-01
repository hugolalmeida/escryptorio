import json
import time
import uuid
from importlib.metadata import version

from cryptolab.config import INTERVALS
from cryptolab.models import Candle
from cryptolab.storage import Store
from cryptolab.history.models import (COLLECTOR_VERSION, HistoryRequest, candle_payload, canonical_history,
                                     canonical_json, missing_ranges, utc_iso)

LEASE_MS = 120_000


class HistoryError(Exception):
    """Código público sanitizado, sem payload ou configuração de rede."""


def now_ms() -> int:
    return int(time.time() * 1000)


def job_request(job: dict) -> HistoryRequest:
    return HistoryRequest(symbol=job["symbol"], interval=job["interval"],
                          start=utc_iso(job["start_time"]), end=utc_iso(job["end_time"]))


class HistoryStore(Store):
    def enqueue(self, request: HistoryRequest) -> dict:
        now = now_ms()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("""SELECT * FROM historical_jobs WHERE exchange='Bybit' AND market='spot'
                AND symbol=? AND interval=? AND start_time=? AND end_time=?""",
                (request.symbol, request.interval, request.start_time, request.end_time)).fetchone()
            if job:
                job_id = job["id"]
                if job["status"] in ("paused", "failed", "incomplete"):
                    db.execute("UPDATE historical_jobs SET status='queued',cancel_requested=0,error_code=NULL,updated_at_ms=? WHERE id=?",
                               (now, job_id))
            else:
                job_id = uuid.uuid4().hex
                db.execute("""INSERT INTO historical_jobs
                    (id,symbol,interval,start_time,end_time,status,created_at_ms,updated_at_ms)
                    VALUES (?,?,?,?,?,'queued',?,?)""",
                    (job_id, request.symbol, request.interval, request.start_time, request.end_time, now, now))
        return self.job(job_id)

    def job(self, job_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM historical_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise HistoryError("JOB_NOT_FOUND")
            result = dict(row)
            result["stored_count"] = db.execute("""SELECT COUNT(*) FROM historical_candles
                WHERE exchange='Bybit' AND market='spot' AND symbol=? AND interval=? AND open_time>=? AND open_time<?""",
                (row["symbol"], row["interval"], row["start_time"], row["end_time"])).fetchone()[0]
            result["expected_count"] = (row["end_time"]-row["start_time"])//INTERVALS[row["interval"]]
            result["runs"] = [dict(r) for r in db.execute("SELECT * FROM historical_runs WHERE job_id=? ORDER BY id", (job_id,))]
            result["gaps"] = [dict(r) for r in db.execute("SELECT start_time,end_time,candle_count FROM historical_gaps WHERE job_id=? ORDER BY start_time", (job_id,))]
            result["pages"] = db.execute("""SELECT COUNT(*) FROM historical_pages p JOIN historical_runs r ON r.id=p.run_id
                WHERE r.job_id=?""", (job_id,)).fetchone()[0]
        return result

    def jobs(self) -> list[dict]:
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM historical_jobs ORDER BY created_at_ms DESC,id DESC LIMIT 50")]
        return [self.job(job_id) for job_id in ids]

    def request_pause(self, job_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT status FROM historical_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise HistoryError("JOB_NOT_FOUND")
            db.execute("""UPDATE historical_jobs SET cancel_requested=1,updated_at_ms=?,
                status=CASE WHEN status='queued' THEN 'paused' ELSE status END WHERE id=? AND status IN ('queued','running')""",
                (now_ms(), job_id))
        return self.job(job_id)

    def claim(self, owner: str, job_id: str | None = None) -> tuple[dict, int] | None:
        now = now_ms()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = db.execute("SELECT * FROM historical_lease WHERE id=1").fetchone()
            if lease and lease["until_ms"] > now:
                return None
            # Recover crashed owners; old processes cannot commit after lease replacement.
            if lease:
                db.execute("UPDATE historical_runs SET status='interrupted',ended_at_ms=?,error_code='LEASE_EXPIRED' WHERE job_id=? AND ended_at_ms IS NULL",
                           (now, lease["job_id"]))
                db.execute("""UPDATE historical_jobs SET status=CASE WHEN cancel_requested=1 THEN 'paused' ELSE 'queued' END,
                    updated_at_ms=? WHERE id=? AND status='running'""", (now, lease["job_id"]))
            query = "SELECT * FROM historical_jobs WHERE status='queued' AND cancel_requested=0"
            row = db.execute(query + (" AND id=?" if job_id else "") + " ORDER BY created_at_ms,id LIMIT 1",
                             (job_id,) if job_id else ()).fetchone()
            if row is None:
                db.execute("DELETE FROM historical_lease WHERE id=1")
                return None
            db.execute("INSERT INTO historical_lease VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,job_id=excluded.job_id,until_ms=excluded.until_ms",
                       (owner, row["id"], now+LEASE_MS))
            db.execute("UPDATE historical_jobs SET status='running',updated_at_ms=?,error_code=NULL WHERE id=?", (now, row["id"]))
            run_id = db.execute("INSERT INTO historical_runs(job_id,started_at_ms,status,collector_version) VALUES (?,?,'running',?)",
                                (row["id"], now, COLLECTOR_VERSION)).lastrowid
        return self.job(row["id"]), run_id

    @staticmethod
    def _owned(db, owner: str):
        row = db.execute("SELECT * FROM historical_lease WHERE id=1 AND owner=? AND until_ms>?", (owner, now_ms())).fetchone()
        if row is None:
            raise HistoryError("LEASE_LOST")
        return row

    def heartbeat(self, owner: str) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = self._owned(db, owner)
            db.execute("UPDATE historical_lease SET until_ms=? WHERE owner=?", (now_ms()+LEASE_MS, owner))
            row = db.execute("SELECT cancel_requested FROM historical_jobs WHERE id=?", (lease["job_id"],)).fetchone()
        return bool(row[0])

    def candles(self, request: HistoryRequest) -> list[Candle]:
        with self.connect() as db:
            rows = db.execute("""SELECT payload FROM historical_candles WHERE exchange='Bybit' AND market='spot'
                AND symbol=? AND interval=? AND open_time>=? AND open_time<? ORDER BY open_time""",
                (request.symbol, request.interval, request.start_time, request.end_time)).fetchall()
        return [Candle(**json.loads(row[0]), closed=True) for row in rows]

    def coverage(self, request: HistoryRequest) -> dict:
        with self.connect() as db:
            rows = db.execute("""SELECT open_time FROM historical_candles WHERE exchange='Bybit' AND market='spot'
                AND symbol=? AND interval=? AND open_time>=? AND open_time<? ORDER BY open_time""",
                (request.symbol, request.interval, request.start_time, request.end_time)).fetchall()
        times = [r[0] for r in rows]
        step = INTERVALS[request.interval]
        gaps = missing_ranges(times, request.start_time, request.end_time, step)
        segments = []
        for stamp in times:
            if segments and segments[-1]["end_time"] == stamp:
                segments[-1]["end_time"] = stamp+step
                segments[-1]["candle_count"] += 1
            else:
                segments.append({"start_time": stamp, "end_time": stamp+step, "candle_count": 1})
        return {"source": "Bybit", "market": "spot", "symbol": request.symbol, "interval": request.interval,
                "start_time": request.start_time, "end_time": request.end_time,
                "stored_count": len(times), "expected_count": request.expected_count,
                "coverage_ratio": len(times)/request.expected_count, "complete": not gaps,
                "segments": segments, "gaps": gaps}

    def save_page(self, owner: str, run_id: int, request: HistoryRequest, page) -> int:
        step, collected = INTERVALS[request.interval], now_ms()
        prepared = [(c.time, candle_payload(c)) for c in page.candles]
        if any(t < request.start_time or t >= request.end_time or t % step or
               (t+step)*1000 > page.source_time_ms for t, _ in prepared):
            raise HistoryError("INVALID_PAGE_RANGE")
        inserted = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = self._owned(db, owner)
            job = db.execute("""SELECT j.* FROM historical_jobs j JOIN historical_runs r ON r.job_id=j.id
                WHERE r.id=? AND r.status='running' AND j.id=?""", (run_id, lease["job_id"])).fetchone()
            if (job is None or job["symbol"] != request.symbol or job["interval"] != request.interval
                    or request.start_time < job["start_time"] or request.end_time > job["end_time"]):
                raise HistoryError("INVALID_RUN_PAGE")
            for stamp, payload in prepared:
                previous = db.execute("""SELECT payload FROM historical_candles WHERE exchange='Bybit' AND market='spot'
                    AND symbol=? AND interval=? AND open_time=?""", (request.symbol, request.interval, stamp)).fetchone()
                if previous and previous[0] != payload:
                    raise HistoryError("CANDLE_CONFLICT")
                if not previous:
                    db.execute("INSERT INTO historical_candles VALUES ('Bybit','spot',?,?,?,?,?,?,?)",
                               (request.symbol, request.interval, stamp, payload, page.source_time_ms, collected, run_id))
                    inserted += 1
            db.execute("INSERT INTO historical_pages(run_id,start_time,end_time,source_time_ms,collected_at_ms,received_count,stored_count,duplicate_count,open_count,outside_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (run_id, request.start_time, request.end_time, page.source_time_ms, collected,
                        page.received_count, inserted, page.duplicate_count+len(prepared)-inserted, page.open_count, page.outside_count))
            db.execute("UPDATE historical_jobs SET updated_at_ms=? WHERE id=(SELECT job_id FROM historical_runs WHERE id=?)", (collected, run_id))
        return inserted

    def finish(self, owner: str, run_id: int, job_id: str, status: str, error: str | None = None, dataset_id: str | None = None):
        job = self.job(job_id)
        coverage = self.coverage(job_request(job))
        now = now_ms()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._owned(db, owner)
            db.execute("DELETE FROM historical_gaps WHERE job_id=?", (job_id,))
            db.executemany("INSERT INTO historical_gaps VALUES (?,?,?,?,?)", [(job_id, g["start_time"], g["end_time"], g["candle_count"], now) for g in coverage["gaps"]])
            db.execute("UPDATE historical_jobs SET status=?,error_code=?,dataset_id=?,updated_at_ms=? WHERE id=?",
                       (status, error, dataset_id, now, job_id))
            db.execute("UPDATE historical_runs SET status=?,error_code=?,ended_at_ms=? WHERE id=?", (status, error, now, run_id))
            db.execute("DELETE FROM historical_lease WHERE owner=?", (owner,))

    def approve(self, owner: str, job: dict) -> str:
        request = job_request(job)
        candles = self.candles(request)
        dataset_id, payload = canonical_history(request, candles)
        now = now_ms()
        # Candle rows are immutable. Prepare outside write lock to keep live worker responsive.
        with self.connect() as db:
            provenance = db.execute("""SELECT MIN(collected_at_ms),MAX(collected_at_ms) FROM historical_candles
                WHERE exchange='Bybit' AND market='spot' AND symbol=? AND interval=? AND open_time>=? AND open_time<?""",
                (request.symbol, request.interval, request.start_time, request.end_time)).fetchone()
            source_runs = [dict(r) for r in db.execute("""SELECT DISTINCT r.id AS run_id,r.collector_version FROM historical_candles c
                JOIN historical_runs r ON r.id=c.run_id WHERE c.exchange='Bybit' AND c.market='spot'
                AND c.symbol=? AND c.interval=? AND c.open_time>=? AND c.open_time<? ORDER BY r.id""",
                (request.symbol, request.interval, request.start_time, request.end_time))]
        manifest = {"dataset_id": dataset_id, "sha256": dataset_id, "schema_version": 1, "source": "Bybit",
            "market": "spot", "symbol": request.symbol, "interval": request.interval,
            "start_time": request.start_time, "end_time": request.end_time, "range_convention": "[start,end)",
            "candle_count": len(candles), "coverage_ratio": 1, "gaps": [], "integrity_status": "approved",
            "approved_at_ms": now, "first_collected_at_ms": provenance[0], "last_collected_at_ms": provenance[1],
            "collector_version": COLLECTOR_VERSION, "pybit_version": version("pybit"), "approval_job_id": job["id"],
            "collection_runs": source_runs}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._owned(db, owner)
            if db.execute("SELECT cancel_requested FROM historical_jobs WHERE id=?", (job["id"],)).fetchone()[0]:
                raise HistoryError("PAUSE_REQUESTED")
            db.execute("INSERT OR IGNORE INTO historical_datasets VALUES (?,?,?,?,?,?,?,?,?)",
                       (dataset_id, request.symbol, request.interval, request.start_time, request.end_time,
                        len(candles), now, canonical_json(manifest), payload))
        return dataset_id

    def datasets(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT manifest FROM historical_datasets ORDER BY approved_at_ms DESC,id DESC LIMIT 50")]
