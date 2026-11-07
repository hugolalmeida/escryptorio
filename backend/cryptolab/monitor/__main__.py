import argparse
import json
from pathlib import Path

from cryptolab.config import Settings
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.service import MonitorError, MonitorService
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.storage import Store


def main():
    parser = argparse.ArgumentParser(description="Monitor offline de snapshots públicos; não envia ordens")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--signals", action="store_true")
    mode.add_argument("--loop", action="store_true")
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--config", help="JSON UTF-8 do bot; obrigatório com --once ou --loop")
    parser.add_argument("--bot", help="Filtro de diagnóstico para --signals")
    parser.add_argument("--poll-seconds", type=int, default=15, help="Intervalo do loop: 10 a 60 segundos")
    parser.add_argument("--recovery-dataset", help="SHA-256 de dataset histórico aprovado")
    args = parser.parse_args()
    if (args.once or args.loop) and not args.config:
        parser.error("--once e --loop exigem --config")
    if not 10 <= args.poll_seconds <= 60:
        parser.error("--poll-seconds deve estar entre 10 e 60")
    settings = Settings.from_env()
    store = Store(settings.database_path)
    store.migrate()
    service = MonitorService(store, settings.stale_after_seconds)
    runtime = MonitorRuntime(store, settings.stale_after_seconds)
    try:
        if args.once or args.loop:
            config = MonitorConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig"))
            if args.loop:
                runtime.loop(config, args.poll_seconds, args.recovery_dataset)
                return 0
            result = runtime.once(config, args.recovery_dataset)
        else:
            result = runtime.status(args.bot) if args.status else service.signals(args.bot)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except MonitorError as exc:
        print(json.dumps({"error":str(exc)}, ensure_ascii=True))
        return 1
    except (OSError, ValueError):
        print(json.dumps({"error":"INVALID_MONITOR_INPUT"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
