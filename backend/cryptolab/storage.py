import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from cryptolab.models import Candle, Snapshot


def canonical_dataset(symbol: str, interval: str, candles: list[Candle]) -> tuple[str, str]:
    payload = json.dumps({"schema_version": 1, "source": "Bybit", "category": "spot", "symbol": symbol,
                          "interval": interval, "candles": [c.model_dump(mode="json") for c in candles if c.closed]},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest(), payload


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            db.commit()
            # Serialize migration checks across startup of API and worker.
            db.execute("BEGIN IMMEDIATE")
            for file in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                if not db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (file.stem,)).fetchone():
                    for statement in file.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            db.execute(statement)
                    db.execute("INSERT INTO schema_migrations VALUES (?)", (file.stem,))

    def save(self, snapshot: Snapshot):
        dataset_id, payload = canonical_dataset(snapshot.symbol, snapshot.interval, snapshot.candles)
        if dataset_id != snapshot.dataset_id:
            raise ValueError("Hash do dataset divergente")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO datasets VALUES (?,?,?,?,?)",
                       (dataset_id, snapshot.symbol, snapshot.interval, snapshot.fetched_at_ms, payload))
            db.execute("INSERT INTO snapshots VALUES (?,?,?) ON CONFLICT(symbol,interval) DO UPDATE SET payload=excluded.payload",
                       (snapshot.symbol, snapshot.interval, snapshot.model_dump_json()))

    def load(self, symbol: str, interval: str) -> Snapshot | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?", (symbol, interval)).fetchone()
        return Snapshot.model_validate_json(row[0]) if row else None

    def status(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM collection_status WHERE id=1").fetchone()
        return dict(row) if row else None

    def record_attempt(self, now: int, error: str | None):
        with self.connect() as db:
            db.execute("""INSERT INTO collection_status VALUES (1,?,?,?)
                ON CONFLICT(id) DO UPDATE SET last_attempt_ms=excluded.last_attempt_ms,
                last_success_ms=COALESCE(excluded.last_success_ms, collection_status.last_success_ms),
                error_code=excluded.error_code""", (now, now if error is None else None, error))
