"""Análise local somente de leitura; não contém execução, rede ou escrita no ledger."""
import hashlib
import json
import re
import sqlite3
import time
from decimal import Decimal as D, ROUND_DOWN, ROUND_UP, localcontext

from cryptolab.config import INTERVALS
from cryptolab.engine.contracts import Decision, InstrumentRules
from cryptolab.history.models import canonical_json, decimal_text
from cryptolab.models import Snapshot
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.service import MonitorError, digest, validated
from cryptolab.paper.ledger import LEDGER_CONTEXT
from cryptolab.paper.planner_models import PlannerBinding, reject_float
from cryptolab.paper.storage import PaperError, PaperStore
from cryptolab.storage import Store

VERSION = "cryptolab-paper-planner/1"


class PlannerError(ValueError):
    pass


def _sha(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _floor(value, step):
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _ceil(value, step):
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


class SignalValidator:
    def __init__(self, store):
        self.store = store

    def validate(self, db, signal_id, binding, now_ms):
        row = db.execute("SELECT * FROM monitor_signals WHERE id=?", (signal_id,)).fetchone()
        if not row:
            raise PlannerError("SIGNAL_NOT_FOUND")
        try:
            signal = json.loads(row["payload"])
            definition = signal["definition"]
            config = MonitorConfig.model_validate(definition["config"])
            if (_sha(row["payload"]) != signal_id or canonical_json(signal) != row["payload"]
                or digest(definition)[0] != row["config_hash"] or signal["config_hash"] != row["config_hash"]
                or row["bot_id"] != config.bot_id or row["candle_time"] != signal["candle_time"]):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise PlannerError("SIGNAL_INTEGRITY_ERROR") from None
        if signal.get("schema_version") != 2:
            raise PlannerError("UNSUPPORTED_SIGNAL_SCHEMA")
        if (signal.get("origin") != "current" or signal.get("eligible_for_future_paper_analysis") is not True
            or signal.get("mode") != "informational_only" or signal.get("position_checked") is not False):
            raise PlannerError("SIGNAL_NOT_ELIGIBLE")
        if row["config_hash"] != binding.monitor_config_hash:
            raise PlannerError("BINDING_CONFIG_MISMATCH")
        try:
            expected = MonitorRuntime(self.store).definition(config)
        except MonitorError:
            raise PlannerError("MONITOR_VERSION_INCOMPATIBLE") from None
        if definition != expected:
            raise PlannerError("MONITOR_VERSION_INCOMPATIBLE")
        step = INTERVALS[config.interval]
        try:
            candle, decision, expiry = (signal[k] for k in ("candle_time", "decision_time", "valid_until"))
            if (any(type(x) is not int for x in (candle, decision, expiry)) or candle < 0 or candle % step
                or decision != candle+step or expiry != decision+step or now_ms < decision*1000):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise PlannerError("SIGNAL_TIME_INVALID") from None
        if now_ms >= expiry*1000:
            raise PlannerError("SIGNAL_EXPIRED")
        runtime = db.execute("SELECT * FROM monitor_runtime WHERE config_hash=?", (row["config_hash"],)).fetchone()
        if (not runtime or runtime["bot_id"] != config.bot_id or runtime["definition"] != canonical_json(definition)
            or runtime["last_candle"] != candle):
            raise PlannerError("MONITOR_CHECKPOINT_MISMATCH")
        # Simultaneous leases or current decisions from another configuration are ambiguous.
        rows = db.execute("SELECT * FROM monitor_runtime WHERE bot_id=? AND config_hash<>?", (config.bot_id, row["config_hash"])).fetchall()
        for other in rows:
            try:
                other_definition = json.loads(other["definition"])
                if digest(other_definition)[0] != other["config_hash"]:
                    raise ValueError()
                other_config = other_definition["config"]
                if MonitorConfig.model_validate(other_config).bot_id != config.bot_id:
                    raise ValueError()
                active = other["lease_owner"] and other["lease_until_ms"] and other["lease_until_ms"] > now_ms
                if other_config != definition["config"] and (active or other["last_candle"] == candle):
                    raise PlannerError("AMBIGUOUS_BOT_CONFIG")
            except PlannerError:
                raise
            except (ValueError, KeyError, TypeError):
                raise PlannerError("MONITOR_RUNTIME_INTEGRITY_ERROR") from None
        return signal, config


class WalletValidator:
    def __init__(self, store):
        self.store = PaperStore(store.path)

    def validate(self, db, wallet_id, binding, config):
        if wallet_id != binding.wallet_id:
            raise PlannerError("BINDING_WALLET_MISMATCH")
        try:
            wallet, _ = self.store._replay(db, wallet_id)
        except PaperError as exc:
            raise PlannerError(str(exc)) from None
        spec = wallet["spec"]
        if wallet["wallet_hash"] != binding.wallet_hash:
            raise PlannerError("BINDING_WALLET_MISMATCH")
        if any(spec[name] != getattr(config, name) for name in ("bot_id", "strategy", "strategy_version", "symbol", "interval")):
            raise PlannerError("WALLET_CONFIG_MISMATCH")
        if wallet["state"]["state"] != "active":
            raise PlannerError("WALLET_PAUSED")
        return wallet


class MarketValidator:
    def __init__(self, max_age=90):
        self.max_age = max_age

    def validate(self, db, signal, config, now_ms):
        row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?", (config.symbol, config.interval)).fetchone()
        if not row:
            raise PlannerError("SNAPSHOT_NOT_FOUND")
        try:
            reject_float(json.loads(row[0])["ticker"])
            snapshot = Snapshot.model_validate_json(row[0])
            candles = validated(snapshot, config, now_ms, self.max_age)
        except (MonitorError, ValueError, KeyError, TypeError) as exc:
            raise PlannerError(str(exc) if isinstance(exc, MonitorError) else "SNAPSHOT_INVALID") from None
        data = db.execute("SELECT payload FROM datasets WHERE id=?", (snapshot.dataset_id,)).fetchone()
        if not data or _sha(data[0]) != snapshot.dataset_id or snapshot.dataset_id != signal["dataset_id"]:
            raise PlannerError("SIGNAL_DATASET_MISMATCH")
        if candles[-1].time != signal["candle_time"]:
            raise PlannerError("SIGNAL_CANDLE_MISMATCH")
        # Recompute the exact informational decision against the verified closed dataset.
        expected = MonitorRuntime(Store(db_path(db)))._signal(config, signal["definition"], signal["config_hash"], candles, snapshot.dataset_id, "current")
        if expected != signal:
            raise PlannerError("SIGNAL_DECISION_MISMATCH")
        raw = snapshot.instrument
        try:
            reject_float(raw)
            stamp = raw["source_time_ms"]
            if type(stamp) is not int or stamp > now_ms+5000 or now_ms-stamp > self.max_age*1000:
                raise PlannerError("STALE_INSTRUMENT")
            ticker_time = snapshot.ticker.source_time_ms
            if ticker_time > now_ms+5000 or now_ms-ticker_time > self.max_age*1000:
                raise PlannerError("STALE_TICKER")
            if raw["symbol"] != config.symbol or raw["status"] != "Trading" or raw["quote_coin"] != "USDT" or snapshot.ticker.symbol != config.symbol:
                raise PlannerError("INSTRUMENT_MISMATCH")
            lot = raw["lot_size_filter"]
            # Spot minOrderQty is deprecated. The smallest positive multiple of
            # basePrecision is a mathematical floor, not an exchange minimum.
            rules = InstrumentRules(symbol=config.symbol, quantity_step=lot["basePrecision"],
                price_tick=raw["price_filter"]["tickSize"], min_quantity=lot["basePrecision"],
                min_notional=lot["minOrderAmt"], max_quantity=lot["maxMarketOrderQty"],
                max_notional=lot.get("maxMarketOrderAmt") or None,
                source_time_ms=stamp, source_hash=digest(raw)[0])
        except PlannerError:
            raise
        except (KeyError, ValueError, TypeError):
            raise PlannerError("INSTRUMENT_LIMITS_INCOMPLETE") from None
        return snapshot, rules


def db_path(db):
    return db.execute("PRAGMA database_list").fetchone()[2]


class VirtualTradePlanner:
    def __init__(self, path, max_age=90, clock=None):
        if not 1 <= max_age <= 300:
            raise ValueError("Invalid freshness")
        self.store = Store(path)
        self.max_age = max_age
        self.clock = clock or (lambda: int(time.time()*1000))

    def plan(self, wallet_id, signal_id, binding):
        binding = PlannerBinding.model_validate(binding if isinstance(binding, dict) else binding.model_dump(mode="json"))
        if not re.fullmatch(r"[a-f0-9]{64}", signal_id) or not re.fullmatch(r"[a-f0-9]{32}", wallet_id):
            raise PlannerError("INVALID_IDENTIFIER")
        first = self._read(wallet_id, signal_id, binding)
        second = self._read(wallet_id, signal_id, binding)
        if first != second:
            raise PlannerError("STATE_CHANGED_RETRY")
        return second

    def _read(self, wallet_id, signal_id, binding):
        now_ms = self.clock()
        # URI read-only, transaction provides one consistent SQLite snapshot without migration.
        uri = self.store.path.resolve().as_uri() + "?mode=ro"
        try:
            db = sqlite3.connect(uri, uri=True, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            signal, config = SignalValidator(self.store).validate(db, signal_id, binding, now_ms)
            wallet = WalletValidator(self.store).validate(db, wallet_id, binding, config)
            snapshot, rules = MarketValidator(self.max_age).validate(db, signal, config, now_ms)
            with localcontext(LEDGER_CONTEXT):
                result = self._propose(signal_id, signal, config, wallet, snapshot, rules, binding, now_ms)
            db.rollback()
            return result
        except sqlite3.Error:
            raise PlannerError("PLANNER_DATABASE_ERROR") from None
        finally:
            if 'db' in locals():
                db.close()

    def _propose(self, signal_id, signal, config, wallet, snapshot, rules, binding, now_ms):
        state, risk = wallet["state"], binding.risk
        cash, quantity = D(state["cash"]), D(state["quantity"])
        if cash < 0 or quantity < 0 or D(state["acquisition_cost"]) < 0:
            raise PlannerError("WALLET_INVALID")
        if state["last_event_time"]*1000 > now_ms:
            raise PlannerError("WALLET_TIME_INVALID")
        if quantity:
            if (state["mark_price"] is None or state["mark_event_time"] is None or
                abs(state["mark_event_time"]*1000 - snapshot.ticker.source_time_ms) > self.max_age*1000 or
                now_ms-state["mark_event_time"]*1000 > self.max_age*1000 or
                state["mark_event_time"]*1000 > now_ms+5000 or D(state["mark_price"]) != snapshot.ticker.price):
                raise PlannerError("WALLET_MARK_STALE_OR_UNVERIFIED")
        equity = cash + quantity*snapshot.ticker.price
        if equity <= 0:
            raise PlannerError("INSUFFICIENT_EQUITY")
        if quantity*snapshot.ticker.price > equity*risk.exposure_fraction:
            raise PlannerError("EXPOSURE_LIMIT_EXCEEDED")
        try:
            decision = Decision.model_validate(signal["if_long"] if quantity else signal["if_flat"])
        except (ValueError, KeyError):
            raise PlannerError("SIGNAL_DECISION_INVALID") from None
        body = {"schema_version":1, "planner_version":VERSION, "signal_id":signal_id, "wallet_id":wallet["wallet_id"],
            "wallet_hash":wallet["wallet_hash"], "wallet_sequence":wallet["sequence"], "wallet_head_hash":wallet["head_hash"],
            "bot_id":config.bot_id, "symbol":config.symbol, "interval":config.interval,
            "strategy":config.strategy, "strategy_version":config.strategy_version,
            "monitor_config_hash":signal["config_hash"], "binding_hash":digest(binding.model_dump(mode="json"))[0],
            "decision_key":digest({"signal_id":signal_id,"wallet_id":wallet["wallet_id"]})[0],
            "risk":binding.risk.model_dump(mode="json"), "action":decision.action.upper(), "reason":decision.reason,
            "decision_candle":signal["candle_time"], "earliest_fill_candle":signal["decision_time"], "expires_at":signal["valid_until"],
            "dataset_id":signal["dataset_id"], "instrument_hash":rules.source_hash, "instrument_source_time_ms":rules.source_time_ms,
            "ticker_price":decimal_text(snapshot.ticker.price),
            "market_source_time_ms":snapshot.source_time_ms, "ticker_source_time_ms":snapshot.ticker.source_time_ms,
            "execution_enabled":False, "needs_revalidation":True,
            "invalidation":"Expiração, mudança de ledger/configuração, preço ou limite; revalidar tudo antes de qualquer etapa futura.",
            "warning":"Proposta condicional; preço, stop e alvo não são fills nem ordens. Gaps podem exceder o risco estimado."}
        if decision.action == "hold":
            body.update(status="HOLD", action="HOLD", planned_quantity=None, reference_price=None)
            return self._finish(body)
        next_candle = next((c for c in snapshot.candles if c.time == signal["decision_time"] and not c.closed), None)
        if next_candle is None or snapshot.ticker.source_time_ms < signal["decision_time"]*1000:
            body.update(status="AWAITING_NEXT_OPEN", planned_quantity=None, reference_price=None,
                        missing=["Candle t+1 e ticker público atualizados", "Revalidar ledger e riscos"])
            return self._finish(body)
        reference = snapshot.ticker.price
        slip, fee = risk.costs.slippage_rate, risk.costs.fee_rate
        estimated_price = _ceil(reference*(D(1)+slip), rules.price_tick) if decision.action == "buy" else _floor(reference*(D(1)-slip), rules.price_tick)
        if estimated_price <= 0:
            raise PlannerError("INVALID_ESTIMATED_PRICE")
        if decision.action == "buy":
            if config.strategy == "buy_hold":
                body.update(status="RISK_STOP_UNAVAILABLE", reference_price=decimal_text(reference), planned_quantity=None,
                            missing=["Política de risco independente para Buy & Hold"])
                return self._finish(body)
            stop = _floor(estimated_price*(D(1)-config.parameters.stop_fraction), rules.price_tick)
            target = _ceil(estimated_price*(D(1)+config.parameters.target_fraction), rules.price_tick)
            if stop <= 0 or stop >= estimated_price:
                raise PlannerError("STOP_INVALID")
            exit_price = _floor(stop*(D(1)-slip), rules.price_tick)
            loss_per_unit = estimated_price-exit_price+fee*(estimated_price+exit_price)
            available = min(cash/(estimated_price*(D(1)+fee)), equity*risk.exposure_fraction/estimated_price,
                            equity*risk.risk_fraction/loss_per_unit, rules.max_quantity)
            planned = _floor(available, rules.quantity_step)
            body.update(planned_stop=decimal_text(stop), planned_target=decimal_text(target),
                        planned_risk=decimal_text(planned*loss_per_unit))
        else:
            planned = _floor(min(quantity, rules.max_quantity), rules.quantity_step)
            self.validate_sell_quantity(planned, quantity)
            body.update(planned_stop=None, planned_target=None, planned_risk=None)
        notional = planned*estimated_price
        if planned <= 0 or planned < rules.min_quantity or notional < rules.min_notional:
            raise PlannerError("INSUFFICIENT_BALANCE_OR_INSTRUMENT_MINIMUM")
        if rules.max_notional is not None and notional > rules.max_notional:
            raise PlannerError("INSTRUMENT_MAX_NOTIONAL_EXCEEDED")
        estimated_fee = notional*fee
        if decision.action == "buy" and notional+estimated_fee > cash:
            raise PlannerError("INSUFFICIENT_BALANCE")
        if decision.action == "sell" and estimated_fee > notional:
            raise PlannerError("SELL_FEE_EXCEEDS_PROCEEDS")
        body.update(status="CONDITIONAL_REVALIDATION_REQUIRED", reference_price=decimal_text(reference),
                    estimated_price=decimal_text(estimated_price), planned_quantity=decimal_text(planned),
                    estimated_fee=decimal_text(estimated_fee), estimated_slippage=decimal_text(abs(estimated_price-reference)*planned),
                    missing=["Revalidar carteira, sinal, preço e limites antes de qualquer simulação futura"])
        return self._finish(body)

    @staticmethod
    def validate_sell_quantity(planned, available):
        if planned <= 0 or planned > available:
            raise PlannerError("SELL_EXCEEDS_POSITION")

    @staticmethod
    def _finish(body):
        identifier, _ = digest(body)
        return {"validation_hash":identifier, **body}
