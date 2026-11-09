"""Comandos locais manuais para pesquisa paper; não há ordens de corretora."""
import argparse
import json
import sqlite3

from cryptolab.config import Settings
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.executor_models import VirtualExecutionRequest
from cryptolab.paper.marking import ExecutionError, PaperMarker, preview_decision
from cryptolab.storage import Store


def main():
    parser = argparse.ArgumentParser(description="Simulação exclusivamente virtual e manual")
    commands = parser.add_subparsers(dest="command",required=True)
    mark = commands.add_parser("mark")
    mark.add_argument("--binding",required=True); mark.add_argument("--signal",required=True)
    mark.add_argument("--key",required=True); mark.add_argument("--paper",action="store_true")
    preview = commands.add_parser("preview"); preview.add_argument("--decision",required=True)
    once = commands.add_parser("once"); once.add_argument("--decision",required=True)
    once.add_argument("--key",required=True); once.add_argument("--paper",action="store_true")
    show = commands.add_parser("show"); show.add_argument("--execution",required=True)
    history = commands.add_parser("history"); history.add_argument("--wallet",required=True)
    commands.add_parser("verify")
    args=parser.parse_args()
    settings=Settings.from_env()
    try:
        if args.command in ("mark","once") and not args.paper:
            raise ExecutionError("EXPLICIT_PAPER_REQUIRED")
        Store(settings.database_path).migrate()
        executor=PaperExecutor(settings.database_path,settings.stale_after_seconds)
        if args.command == "mark":
            result=PaperMarker(settings.database_path,settings.stale_after_seconds).mark(args.binding,args.signal,args.key)
        elif args.command == "preview":
            result=preview_decision(settings.database_path,args.decision,settings.stale_after_seconds)
        elif args.command == "once":
            result=executor.execute(VirtualExecutionRequest(decision_id=args.decision,idempotency_key=args.key),paper=True)
        elif args.command == "show": result=executor.receipt(args.execution)
        elif args.command == "history": result=executor.history(args.wallet)
        else: result=executor.verify_integrity()
        print(json.dumps(result,ensure_ascii=True,indent=2))
        return 0
    except ExecutionError as exc:
        print(json.dumps({"error":str(exc),"live_execution_enabled":False}))
        return 1
    except (ValueError,sqlite3.Error,OSError):
        print(json.dumps({"error":"PAPER_INPUT_OR_DATABASE_ERROR","live_execution_enabled":False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
