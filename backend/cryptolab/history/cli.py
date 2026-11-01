import argparse
import json

from cryptolab.config import Settings
from cryptolab.history.collector import HistoricalCollector
from cryptolab.history.models import HistoryRequest
from cryptolab.history.reader import DatasetReader
from cryptolab.history.source import HistoricalBybit
from cryptolab.history.storage import HistoryError, HistoryStore


def main():
    parser = argparse.ArgumentParser(description="CryptoLab · histórico público Spot e datasets offline")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("collect", "coverage"):
        sub = commands.add_parser(name)
        sub.add_argument("--symbol", required=True, choices=("BTCUSDT", "ETHUSDT"))
        sub.add_argument("--interval", required=True, choices=("15", "60", "240", "D"))
        sub.add_argument("--start", required=True, help="Data UTC ou ISO com offset, início inclusivo")
        sub.add_argument("--end", required=True, help="Data UTC ou ISO com offset, fim exclusivo")
    commands.add_parser("datasets")
    read = commands.add_parser("read")
    read.add_argument("--dataset", required=True)
    read.add_argument("--start", help="Recorte opcional UTC, inclusivo")
    read.add_argument("--end", help="Recorte opcional UTC, exclusivo")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = HistoryStore(settings.database_path)
    store.migrate()
    try:
        if args.command in ("collect", "coverage"):
            request = HistoryRequest(symbol=args.symbol, interval=args.interval, start=args.start, end=args.end)
            if args.command == "coverage":
                result = store.coverage(request)
            else:
                job = store.enqueue(request)
                if job["status"] == "completed":
                    result = job
                else:
                    def progress(current):
                        print(f"job={current['id']} candles={current['stored_count']}/{current['expected_count']} páginas={current['pages']}", flush=True)
                    result = HistoricalCollector(store, HistoricalBybit(), on_progress=progress).run(job["id"])
                    if result is None:
                        print(json.dumps({"job_id": job["id"], "status": "queued", "detail": "Coletor ocupado; job persistido para o worker histórico."}))
                        return 2
        elif args.command == "datasets":
            result = store.datasets()
        else:
            from cryptolab.history.models import parse_utc
            data = DatasetReader(store).read(args.dataset, parse_utc(args.start) if args.start else None,
                                             parse_utc(args.end) if args.end else None)
            result = {"reference_hash": data.reference_hash, "manifest": data.manifest, "start_time": data.start_time,
                "end_time": data.end_time, "candles": [c.model_dump(mode="json") for c in data.candles]}
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if args.command != "collect" or result["status"] == "completed" else 2
    except (HistoryError, ValueError) as exc:
        code = str(exc) if isinstance(exc, HistoryError) else "INVALID_UTC_RANGE"
        print(json.dumps({"error_code": code}))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "paused", "detail": "Cancelado; retome com o mesmo comando."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
