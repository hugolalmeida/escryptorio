"""Consulta local apenas; não ativa carteiras e não cria operações."""
import argparse
import json
from pathlib import Path

from cryptolab.config import Settings
from cryptolab.monitor.service import digest
from cryptolab.paper.planner import PlannerError, VirtualTradePlanner
from cryptolab.paper.planner_models import PlannerBinding


def main():
    parser = argparse.ArgumentParser(description="Planejamento virtual condicional, somente leitura")
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--binding", required=True, help="JSON UTF-8 de vínculo e risco explícitos")
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        binding = PlannerBinding.model_validate_json(Path(args.binding).read_text(encoding="utf-8-sig"))
        result = VirtualTradePlanner(settings.database_path, settings.stale_after_seconds).plan(args.wallet, args.signal, binding)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except PlannerError as exc:
        result = {"status":"BLOCKED", "error":str(exc), "reason":str(exc),
                  "wallet_id":args.wallet, "signal_id":args.signal, "execution_enabled":False}
        if "binding" in locals():
            result["binding_hash"] = digest(binding.model_dump(mode="json"))[0]
        print(json.dumps(result, ensure_ascii=True))
        return 1
    except (OSError, ValueError):
        print(json.dumps({"status":"BLOCKED", "error":"INVALID_PLANNER_INPUT", "execution_enabled":False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
