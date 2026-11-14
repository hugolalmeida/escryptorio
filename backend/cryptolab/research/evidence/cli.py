"""Manual, offline-only evidence export and verification."""
import argparse
import json
import time

from cryptolab.config import Settings
from .bundle import export_bundle, verify_bundle
from .core import EvidenceError, package, report, source_from_db


def main():
    parser = argparse.ArgumentParser(description="Offline deterministic research evidence")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source", required=True)
    build.add_argument("--source-id", required=True)
    build.add_argument("--as-of-ms", required=True, type=int)
    build.add_argument("--mode", choices=("RETROSPECTIVE", "RECENT_OBSERVATION"), default="RETROSPECTIVE")
    build.add_argument("--output", required=True)
    build.add_argument("--database")
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle", required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            if args.source != "approved-history":
                raise EvidenceError("UNSUPPORTED_SOURCE")
            settings = Settings.from_env()
            source = source_from_db(args.database or settings.database_path, args.source_id)
            now = time.time_ns() // 1_000_000
            pkg = package(source, args.mode, args.as_of_ms, now)
            rep = report(pkg, source, now)
            export_bundle(args.output, pkg, rep, source)
            result = verify_bundle(args.output)
        else:
            result = verify_bundle(args.bundle)
        print(json.dumps(result, sort_keys=True))
    except EvidenceError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    except (OSError, RuntimeError):
        print(json.dumps({"error": "EVIDENCE_OPERATION_FAILED"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
