"""Offline research CLI; no SDK import or network calls."""
import argparse
import json
from pathlib import Path

from cryptolab.config import Settings
from cryptolab.history.storage import HistoryStore, HistoryError
from cryptolab.research.service import ProtocolRequest, ResearchService, RunRequest


def main():
    parser = argparse.ArgumentParser(description="CryptoLab: backtests locais, sem ordens reais")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("datasets")
    commands.add_parser("runs")
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--config", required=True, help="JSON UTF-8 com dataset, estratégia, parâmetros e janelas UTC em segundos")
    run = commands.add_parser("run")
    run.add_argument("--protocol", required=True)
    run.add_argument("--partition", choices=["train", "validation", "test"], required=True)
    for name in ("show", "verify", "trades"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--run", required=True)
    args = parser.parse_args()
    store = HistoryStore(Settings.from_env().database_path)
    store.migrate()
    service = ResearchService(store)
    try:
        if args.command == "datasets":
            result = store.datasets()
        elif args.command == "runs":
            result = service.runs()
        elif args.command == "freeze":
            result = service.freeze(ProtocolRequest.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig")))
        elif args.command == "run":
            result = service.run(RunRequest(protocol_id=args.protocol, partition=args.partition))
        elif args.command == "verify":
            result = service.verify(args.run)
        else:
            result = service.result(args.run)
            if args.command == "trades":
                result = result["simulation"]["trades"]
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, HistoryError, OSError):
        print("Pesquisa recusada: confira configuração, dataset, warm-up e versão do código.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
