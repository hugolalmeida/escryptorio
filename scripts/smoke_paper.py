"""Diagnóstico opt-in com banco novo; nunca executa fills ou usa conta privada."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cryptolab.config import INTERVALS, SYMBOLS, Settings
from cryptolab.engine.contracts import InstrumentRules
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.service import validated
from cryptolab.paper.decisions import DecisionService
from cryptolab.paper.executor import PaperExecutor
from cryptolab.paper.models import StateRecord, WalletSpec
from cryptolab.paper.planner import VirtualTradePlanner
from cryptolab.paper.storage import PaperStore
from cryptolab.storage import Store


def isolated_database():
    """Cria diretório exclusivo; nunca aceita caminho de banco fornecido pelo usuário."""
    directory = Path(tempfile.mkdtemp(prefix="escryptorio-smoke-")).resolve(strict=True)
    database = directory / "smoke.sqlite3"
    default = (ROOT / "data" / "cryptolab.sqlite3").resolve()
    if database.exists() or database.resolve() == default or directory == ROOT or ROOT in directory.parents:
        raise ValueError("UNSAFE_DATABASE_PATH")
    return database


def run(public=False, activate=False):
    if os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "false":
        raise ValueError("LIVE_TRADING_MUST_BE_DISABLED")
    if os.getenv("PAPER_SIMULATION_ENABLED", "false").lower() != "false":
        raise ValueError("PAPER_SIMULATION_MUST_BE_DISABLED")
    if activate and not public:
        raise ValueError("PUBLIC_COLLECTION_REQUIRED")
    path = isolated_database()
    env = os.environ.copy()
    env.update(CRYPTOLAB_DATABASE=str(path), LIVE_TRADING_ENABLED="false", PAPER_SIMULATION_ENABLED="false", PYTHONPATH=str(ROOT / "backend"))
    # Every local component receives exactly the same explicit path.
    previous = os.environ.get("CRYPTOLAB_DATABASE")
    os.environ["CRYPTOLAB_DATABASE"] = str(path)
    report = {"database": str(path), "utc": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
              "result": "NOT_RUN", "public_collection": "NOT_RUN", "fill": "NOT_RUN"}
    try:
        assert Settings.from_env().database_path.resolve() == path
        store = Store(path)
        store.migrate()
        if not public:
            report["integrity"] = PaperExecutor(path).verify_integrity()
            return report
        try:
            worker = subprocess.run([sys.executable, "-m", "cryptolab.worker", "--once"], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            report.update(result="FAILED", public_collection="WORKER_TIMEOUT")
            return report
        if worker.returncode:
            report.update(result="FAILED", public_collection="BYBIT_UNAVAILABLE_OR_INVALID")
            return report
        now = int(time.time() * 1000)
        snapshots = []
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                snap = store.load(symbol, interval)
                if snap is None:
                    raise ValueError("MISSING_SNAPSHOT")
                config = MonitorConfig(bot_id="smoke-validation", symbol=symbol, interval=interval, strategy="trend")
                closed = validated(snap, config, now, 90)
                with store.connect() as db:
                    row = db.execute("SELECT payload FROM datasets WHERE id=?", (snap.dataset_id,)).fetchone()
                if not row or hashlib.sha256(row[0].encode()).hexdigest() != snap.dataset_id:
                    raise ValueError("DATASET_INTEGRITY_ERROR")
                raw = snap.instrument
                ticker_ms = snap.ticker.source_time_ms
                instrument_ms = raw["source_time_ms"]
                if (snap.ticker.symbol != symbol or raw["symbol"] != symbol or raw["status"] != "Trading"
                    or raw["quote_coin"] != "USDT" or any(t > now + 5000 or now - t > 90000 for t in (ticker_ms, instrument_ms))):
                    raise ValueError("INVALID_MARKET_METADATA")
                lot = raw["lot_size_filter"]
                InstrumentRules(symbol=symbol, quantity_step=lot["basePrecision"], price_tick=raw["price_filter"]["tickSize"],
                    min_quantity=lot["basePrecision"], min_notional=lot["minOrderAmt"], max_quantity=lot["maxMarketOrderQty"],
                    source_time_ms=instrument_ms, source_hash="0" * 64)
                snapshots.append({"symbol": symbol, "interval": interval, "dataset_id": snap.dataset_id,
                    "source_time_ms": snap.source_time_ms, "fetched_at_ms": snap.fetched_at_ms,
                    "age_ms": now - snap.source_time_ms, "closed_candles": len(closed)})
        report.update(public_collection="PASS", snapshots=snapshots)
        config = MonitorConfig(bot_id="smoke-" + uuid.uuid4().hex, symbol="BTCUSDT", interval="60", strategy="trend")
        runtime = MonitorRuntime(store)
        signal = runtime.once(config)
        if runtime.once(config)["id"] != signal["id"]:
            raise ValueError("MONITOR_IDEMPOTENCY_ERROR")
        if signal["schema_version"] != 2 or signal["origin"] != "current" or signal["mode"] != "informational_only":
            raise ValueError("SIGNAL_NOT_CURRENT")
        report["signal"] = {k: signal[k] for k in ("id", "schema_version", "origin", "mode", "config_hash", "dataset_id", "if_flat")}
        report["monitor_status"] = runtime.status(config.bot_id)
        paper = PaperStore(path)
        wallet = paper.create_wallet(WalletSpec(bot_id=config.bot_id, strategy="trend", symbol="BTCUSDT", interval="60",
                                    initial_capital="1000", opened_at=int(time.time())), "smoke-create")
        verify = lambda: PaperExecutor(path).verify_integrity()
        report["integrity"] = verify()
        report["wallet"] = wallet
        if not activate:
            report["result"] = "BLOCKED_EXPECTED"
            report["reason"] = "WALLET_PAUSED_EXPLICIT_ACTIVATION_REQUIRED"
            return report
        paper.append(wallet["wallet_id"], "smoke-activate", StateRecord(state="active", event_time=int(time.time())))
        verify()
        binding = {"wallet_id": wallet["wallet_id"], "wallet_hash": wallet["wallet_hash"], "monitor_config_hash": signal["config_hash"],
                   "risk": {"risk_fraction": "0.01", "exposure_fraction": "0.10", "costs": {"fee_rate": "0.001", "slippage_rate": "0.0005"}}}
        decisions = DecisionService(path)
        registered = decisions.register_binding(binding)
        verify()
        active = decisions.activate_binding(registered["id"])
        verify()
        report["binding"] = {"id": active["id"], "state": active["state"]}
        before = paper.wallet(wallet["wallet_id"])
        proposal = VirtualTradePlanner(path).plan(wallet["wallet_id"], signal["id"], binding)
        if paper.wallet(wallet["wallet_id"]) != before:
            raise ValueError("PLANNER_MUTATED_LEDGER")
        report["proposal"] = proposal
        if proposal["status"] in ("HOLD", "CONDITIONAL_REVALIDATION_REQUIRED"):
            decision = decisions.record_decision(active["id"], signal["id"], proposal["validation_hash"])
            report["decision"] = {"id": decision["id"], "state": decision["state"]}
            verify()
        report["wallet"] = paper.wallet(wallet["wallet_id"])
        report["integrity"] = verify()
        report["result"] = "NO_ELIGIBLE_TRADE" if proposal["action"] == "HOLD" else "BLOCKED_EXPECTED"
        report["reason"] = "MANUAL_FILL_NOT_IMPLEMENTED_IN_SMOKE" if proposal["action"] != "HOLD" else "HOLD"
        return report
    finally:
        if previous is None:
            os.environ.pop("CRYPTOLAB_DATABASE", None)
        else:
            os.environ["CRYPTOLAB_DATABASE"] = previous


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico paper isolado, sem fills")
    parser.add_argument("--public", action="store_true", help="permite uma coleta pública")
    parser.add_argument("--activate-wallet", action="store_true", help="ativa apenas a carteira descartável criada nesta execução")
    args = parser.parse_args()
    try:
        result = run(args.public, args.activate_wallet)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 1 if result["result"] == "FAILED" else 0
    except Exception:
        print(json.dumps({"result": "FAILED", "error": "SMOKE_VALIDATION_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
