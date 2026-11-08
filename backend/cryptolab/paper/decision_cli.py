"""CLI local de vínculo e auditoria; não executa operações financeiras."""
import argparse
import json
import sqlite3
from pathlib import Path

from cryptolab.config import Settings
from cryptolab.paper.decisions import DecisionError, DecisionService
from cryptolab.paper.storage import PaperError
from cryptolab.storage import Store


def main():
    parser = argparse.ArgumentParser(description="Vínculos e decisões virtuais; sem fills ou ordens")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register-binding")
    register.add_argument("--binding", required=True)
    for name in ("get-binding","activate-binding","disable-binding"):
        command = commands.add_parser(name)
        command.add_argument("--id", required=True)
        if name == "disable-binding": command.add_argument("--reason", required=True)
    commands.add_parser("list-bindings")
    record = commands.add_parser("record-decision")
    record.add_argument("--binding-id", required=True)
    record.add_argument("--signal", required=True)
    record.add_argument("--validation-hash", required=True)
    for name in ("get-decision","invalidate-decision"):
        command = commands.add_parser(name)
        command.add_argument("--id", required=True)
        if name == "invalidate-decision": command.add_argument("--reason", required=True)
    commands.add_parser("verify")
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        Store(settings.database_path).migrate()
        service = DecisionService(settings.database_path, settings.stale_after_seconds)
        if args.command == "register-binding":
            result = service.register_binding(json.loads(Path(args.binding).read_text(encoding="utf-8-sig")))
        elif args.command == "get-binding": result = service.get_binding(args.id)
        elif args.command == "activate-binding": result = service.activate_binding(args.id)
        elif args.command == "disable-binding": result = service.disable_binding(args.id,args.reason)
        elif args.command == "list-bindings": result = service.list_bindings()
        elif args.command == "record-decision": result = service.record_decision(args.binding_id,args.signal,args.validation_hash)
        elif args.command == "get-decision": result = service.get_decision(args.id)
        elif args.command == "invalidate-decision": result = service.invalidate_decision(args.id,args.reason)
        else: result = service.verify_integrity()
        print(json.dumps(result,ensure_ascii=True,indent=2))
        return 0
    except (DecisionError, PaperError) as exc:
        print(json.dumps({"error":str(exc),"execution_enabled":False}))
        return 1
    except (OSError,ValueError):
        print(json.dumps({"error":"INVALID_DECISION_INPUT","execution_enabled":False}))
        return 1
    except sqlite3.Error:
        print(json.dumps({"error":"DECISION_DATABASE_ERROR","execution_enabled":False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
