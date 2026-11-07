import argparse
import json
from pathlib import Path

from cryptolab.config import Settings
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.service import MonitorError, MonitorService
from cryptolab.storage import Store


def main():
    parser = argparse.ArgumentParser(description="Monitor offline de snapshots públicos; não envia ordens")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--signals", action="store_true")
    parser.add_argument("--config", help="JSON UTF-8 do bot; obrigatório com --once")
    parser.add_argument("--bot", help="Filtro de diagnóstico para --signals")
    args = parser.parse_args()
    if args.once and not args.config:
        parser.error("--once exige --config")
    settings = Settings.from_env()
    store = Store(settings.database_path)
    store.migrate()
    service = MonitorService(store, settings.stale_after_seconds)
    try:
        result = service.evaluate(MonitorConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig"))) if args.once else service.signals(args.bot)
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
