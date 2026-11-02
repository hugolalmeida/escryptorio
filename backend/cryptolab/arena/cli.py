"""Comandos exclusivamente locais, sem cliente de rede."""
import argparse
import json
from pathlib import Path

from cryptolab.arena.models import ArenaConfig
from cryptolab.arena.service import ArenaService
from cryptolab.config import Settings
from cryptolab.history.storage import HistoryError, HistoryStore


def main():
    parser = argparse.ArgumentParser(description="Arena histórica offline, sem ordens reais")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    create = commands.add_parser("create")
    create.add_argument("--config", required=True, help="Arquivo JSON UTF-8 com configuração da competição")
    for name in ("show", "execute", "result"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--experiment", required=True)
    args = parser.parse_args()
    store = HistoryStore(Settings.from_env().database_path)
    store.migrate()
    service = ArenaService(store)
    try:
        if args.command == "create":
            result = service.create(ArenaConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig")))
        elif args.command == "list":
            result = service.experiments()
        else:
            result = getattr(service, args.command if args.command != "show" else "experiment")(args.experiment)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, HistoryError, OSError):
        print("Arena recusada: confira dataset, protocolos, janelas e versão do motor.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
