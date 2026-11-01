import argparse
import logging
import time

from cryptolab.bybit import MarketDataError, PublicBybit
from cryptolab.config import INTERVALS, SYMBOLS, Settings
from cryptolab.storage import Store

logger = logging.getLogger("cryptolab.worker")


def collect(store: Store, client: PublicBybit) -> bool:
    errors = []
    for symbol in SYMBOLS:
        try:
            ticker, instrument = client.ticker(symbol), client.instrument(symbol)
        except MarketDataError as exc:
            errors.append(str(exc))
            logger.warning("Coleta indisponível: %s %s", symbol, str(exc))
            continue
        for interval in INTERVALS:
            try:
                snapshot = client.snapshot(symbol, interval, ticker, instrument)
                store.save(snapshot)
                logger.info("Snapshot salvo: %s %s %s", symbol, interval, snapshot.dataset_id[:12])
            except MarketDataError as exc:
                errors.append(str(exc))
                logger.warning("Coleta indisponível: %s %s %s", symbol, interval, str(exc))
    store.record_attempt(int(time.time() * 1000), errors[0] if errors else None)
    return not errors


def main():
    parser = argparse.ArgumentParser(description="Coletor público Bybit Spot, sem credenciais")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_path)
    store.migrate()
    client = PublicBybit()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        while True:
            started = time.monotonic()
            success = collect(store, client)
            if args.once:
                raise SystemExit(0 if success else 1)
            time.sleep(max(1, settings.poll_seconds - (time.monotonic() - started)))
    except KeyboardInterrupt:
        logger.info("Coletor encerrado")


if __name__ == "__main__":
    main()
