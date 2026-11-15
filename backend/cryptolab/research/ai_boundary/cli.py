"""Explicit local inspection and development mock, with sanitized failures."""
import argparse
import json

from ..evidence.core import EvidenceError
from .context import build_context
from .runtime import BudgetSession, run_mock


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise EvidenceError("ARGUMENT_INVALID")


def main(argv=None):
    parser = Parser()
    parser.add_argument("operation", choices=("inspect-context", "run-mock"))
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--mode", choices=("DEVELOPMENT_MOCK", "ISOLATED_RESEARCH"), default="ISOLATED_RESEARCH")
    parser.add_argument("--request-id", default="manual-1")
    try:
        args = parser.parse_args(argv)
        context = build_context(args.bundle)
        if args.operation == "inspect-context":
            result = context.model_dump(mode="json")
        else:
            budget = BudgetSession()
            result = run_mock(context, args.request_id, budget, mode=args.mode)
            result["budget"] = budget.usage()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except EvidenceError as exc:
        print(json.dumps({"status": "UNAVAILABLE", "code": str(exc)}))
        return 2
    except OSError:
        print(json.dumps({"status": "UNAVAILABLE", "code": "RESEARCH_IO_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
