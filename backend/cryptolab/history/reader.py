import hashlib
import json
from dataclasses import dataclass

from cryptolab.config import INTERVALS
from cryptolab.models import Candle
from cryptolab.history.models import HistoryRequest, canonical_history, utc_iso
from cryptolab.history.storage import HistoryError, HistoryStore


@dataclass(frozen=True)
class ResearchDataset:
    reference_hash: str
    manifest: dict
    candles: tuple[Candle, ...]
    start_time: int
    end_time: int


class DatasetReader:
    """Leitura offline verificada para o futuro motor: apenas datasets aprovados e sem rede."""

    def __init__(self, store: HistoryStore):
        self.store = store

    def read(self, dataset_id: str, start_time: int | None = None, end_time: int | None = None) -> ResearchDataset:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM historical_datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None:
            raise HistoryError("DATASET_NOT_FOUND")
        if hashlib.sha256(row["payload"].encode("utf-8")).hexdigest() != dataset_id:
            raise HistoryError("DATASET_HASH_MISMATCH")
        try:
            payload, manifest = json.loads(row["payload"]), json.loads(row["manifest"])
            request = HistoryRequest(symbol=payload["symbol"], interval=payload["interval"],
                start=utc_iso(payload["start_time"]), end=utc_iso(payload["end_time"]))
            candles = [Candle(**c, closed=True) for c in payload["candles"]]
            recomputed, _ = canonical_history(request, candles)
            if (recomputed != dataset_id or payload["source"] != "Bybit" or payload["market"] != "spot"
                or payload["schema_version"] != 1 or manifest["integrity_status"] != "approved"
                or manifest["sha256"] != dataset_id or manifest["dataset_id"] != dataset_id
                or manifest["gaps"] or manifest["coverage_ratio"] != 1
                or manifest["candle_count"] != len(candles)
                or any(manifest[k] != payload[k] for k in ("schema_version", "symbol", "interval", "start_time", "end_time", "source", "market"))):
                raise ValueError("manifest")
        except (KeyError, ValueError, TypeError):
            raise HistoryError("DATASET_INTEGRITY_ERROR") from None
        start = request.start_time if start_time is None else start_time
        end = request.end_time if end_time is None else end_time
        step = INTERVALS[request.interval]
        if start < request.start_time or end > request.end_time or end <= start or start % step or end % step:
            raise HistoryError("INVALID_DATASET_RANGE")
        return ResearchDataset(dataset_id, manifest, tuple(c for c in candles if start <= c.time < end), start, end)
