import argparse
import logging
import time

from cryptolab.config import Settings
from cryptolab.history.collector import HistoricalCollector
from cryptolab.history.source import HistoricalBybit
from cryptolab.history.storage import HistoryStore


def main():
    parser = argparse.ArgumentParser(description="Worker independente de jobs históricos públicos")
    parser.add_argument("--once", action="store_true", help="Executa no máximo um job pendente")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = HistoryStore(settings.database_path)
    store.migrate()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collector = HistoricalCollector(store, HistoricalBybit())
    try:
        while True:
            job = collector.run()
            if job:
                logging.info("Histórico job=%s estado=%s candles=%s/%s erro=%s", job["id"], job["status"],
                             job["stored_count"], job["expected_count"], job["error_code"])
            if args.once:
                return
            time.sleep(2)
    except KeyboardInterrupt:
        logging.info("Worker histórico encerrado; páginas confirmadas preservadas")


if __name__ == "__main__":
    main()
