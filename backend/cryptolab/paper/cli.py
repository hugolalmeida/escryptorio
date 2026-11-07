"""Criação e consulta local; não registra fills nem dispara execuções."""
import argparse
import json

from cryptolab.config import Settings
from cryptolab.paper.models import WalletSpec
from cryptolab.paper.storage import PaperError, PaperStore


def main():
    parser = argparse.ArgumentParser(description="Carteiras virtuais locais; nenhuma conta ou ordem real")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--bot", required=True)
    create.add_argument("--strategy", choices=["trend","rsi","breakout","buy_hold"], required=True)
    create.add_argument("--symbol", choices=["BTCUSDT","ETHUSDT"], required=True)
    create.add_argument("--interval", choices=["15","60","240","D"], required=True)
    create.add_argument("--capital", required=True)
    create.add_argument("--key", required=True, help="chave de idempotência da criação")
    # Explicit timestamp allows the exact same create request to be retried.
    create.add_argument("--opened-at", required=True, type=int, help="segundos UTC")
    commands.add_parser("list")
    for name in ("show", "ledger", "verify"):
        item = commands.add_parser(name)
        item.add_argument("--wallet", required=True)
    args = parser.parse_args()
    store = PaperStore(Settings.from_env().database_path)
    store.migrate()
    try:
        if args.command == "create":
            result = store.create_wallet(WalletSpec(bot_id=args.bot,strategy=args.strategy,symbol=args.symbol,
                interval=args.interval,initial_capital=args.capital,opened_at=args.opened_at), args.key)
        elif args.command == "list":
            result = store.wallets()
        elif args.command == "ledger":
            result = store.events(args.wallet)
        else:
            view = store.wallet(args.wallet)
            result = {"wallet_id":args.wallet,"sequence":view["sequence"],"head_hash":view["head_hash"],"valid":True} if args.command == "verify" else view
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, PaperError):
        print("Carteira recusada: verifique configuração, idempotência e integridade do ledger.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
