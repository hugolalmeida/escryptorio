"""Orquestra quatro protocolos existentes; não contém fórmulas de simulação."""
import hashlib
import json
from decimal import Decimal, localcontext

from cryptolab.arena.models import ARENA_VERSION, PARTITIONS, STRATEGIES, ArenaConfig, ArenaExperiment, ProtocolIds
from cryptolab.history.reader import DatasetReader
from cryptolab.history.storage import HistoryStore
from cryptolab.research.service import LEGACY_COMPATIBLE, ProtocolRequest, ResearchService, RunRequest, digest


class ArenaError(ValueError):
    pass


def rank_entries(entries: list[dict]) -> list[dict]:
    # Sort by Decimal directly: unary minus would round under the ambient context.
    entries = sorted(entries, key=lambda entry: entry["strategy"])
    entries.sort(key=lambda entry: Decimal(entry["net_return_pct"]), reverse=True)
    previous = None
    rank = 0
    for index, entry in enumerate(entries, 1):
        value = Decimal(entry["net_return_pct"])
        if previous is None or value != previous:
            rank = index
        entry["rank"] = rank
        previous = value
    return entries


class ArenaService:
    def __init__(self, store: HistoryStore):
        self.store = store
        self.research = ResearchService(store)

    @staticmethod
    def _protocol_request(config: ArenaConfig, strategy: str) -> ProtocolRequest:
        return ProtocolRequest(dataset_hash=config.dataset_hash, strategy=strategy,
            parameters=getattr(config.strategies, strategy).parameters, config=config.backtest,
            train_start=config.train_start, train_end=config.train_end,
            validation_end=config.validation_end, test_end=config.test_end)

    def _check_protocols(self, config: ArenaConfig, ids: ProtocolIds) -> dict:
        data = DatasetReader(self.store).read(config.dataset_hash)
        if data.manifest["symbol"] != config.symbol or data.manifest["interval"] != config.interval:
            raise ArenaError("DATASET_MARKET_MISMATCH")
        protocols = {}
        for strategy in STRATEGIES:
            item = self.research.protocol(getattr(ids, strategy))
            if ProtocolRequest.model_validate(item["request"]) != self._protocol_request(config, strategy):
                raise ArenaError("PROTOCOL_CONDITIONS_MISMATCH")
            protocols[strategy] = item
        first = protocols[STRATEGIES[0]]
        def effective_hash(item):
            # Explicit legacy bridge is already audited and enforced by ResearchService.run.
            return LEGACY_COMPATIBLE.get(item["code_hash"], item["code_hash"])
        if any(p["instrument"] != first["instrument"] or p["engine_version"] != first["engine_version"]
               or effective_hash(p) != effective_hash(first) for p in protocols.values()):
            raise ArenaError("PROTOCOL_ENGINE_OR_INSTRUMENT_MISMATCH")
        return protocols

    def create(self, config: ArenaConfig) -> dict:
        config_hash = digest(config.model_dump(mode="json"))[0]
        with self.store.connect() as db:
            row = db.execute("SELECT id FROM arena_experiments WHERE config_hash=?", (config_hash,)).fetchone()
        if row:
            experiment = self.experiment(row[0])
            if experiment["config"] != config.model_dump(mode="json"):
                raise ArenaError("ARENA_CONFIG_HASH_MISMATCH")
            return experiment
        dataset = DatasetReader(self.store).read(config.dataset_hash)
        if dataset.manifest["symbol"] != config.symbol or dataset.manifest["interval"] != config.interval:
            raise ArenaError("DATASET_MARKET_MISMATCH")
        if config.protocol_ids:
            ids = config.protocol_ids
        else:
            ids = ProtocolIds(**{strategy: self.research.freeze(self._protocol_request(config, strategy))["id"]
                                 for strategy in STRATEGIES})
        self._check_protocols(config, ids)
        exp = ArenaExperiment(config=config, protocol_ids=ids)
        identifier, payload = digest(exp.model_dump(mode="json"))
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO arena_experiments(id,config_hash,payload) VALUES (?,?,?)",
                       (identifier, config_hash, payload))
            row = db.execute("SELECT id FROM arena_experiments WHERE config_hash=?", (config_hash,)).fetchone()
        # A concurrent request can freeze different instrument snapshots. The first persisted
        # experiment wins; verify it instead of silently replacing it.
        return self.experiment(row[0])

    def experiment(self, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute("SELECT payload,config_hash FROM arena_experiments WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ArenaError("ARENA_EXPERIMENT_NOT_FOUND")
        if hashlib.sha256(row["payload"].encode("utf-8")).hexdigest() != identifier:
            raise ArenaError("ARENA_EXPERIMENT_HASH_MISMATCH")
        try:
            payload = json.loads(row["payload"])
            exp = ArenaExperiment.model_validate(payload)
            if digest(exp.config.model_dump(mode="json"))[0] != row["config_hash"]:
                raise ArenaError("ARENA_CONFIG_HASH_MISMATCH")
            self._check_protocols(exp.config, exp.protocol_ids)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ArenaError):
                raise
            raise ArenaError("ARENA_EXPERIMENT_INVALID") from None
        return {"id": identifier, **payload}

    def experiments(self) -> list[dict]:
        with self.store.connect() as db:
            rows = db.execute("SELECT id,created_at FROM arena_experiments ORDER BY created_at DESC,id DESC LIMIT 50").fetchall()
        return [dict(row) for row in rows]

    def execute(self, identifier: str) -> dict:
        exp = self.experiment(identifier)
        ids = exp["protocol_ids"]
        runs = {}
        # Do not use a strategy's future window to choose parameters. All protocols
        # are frozen before any of these calls, and each replay starts with fresh capital.
        for partition in PARTITIONS:
            runs[partition] = {}
            for strategy in STRATEGIES:
                result = self.research.run(RunRequest(protocol_id=ids[strategy], partition=partition))
                runs[partition][strategy] = result["id"]
        result = self._aggregate(exp, runs)
        result_id, payload = digest(result)
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO arena_results(id,experiment_id,payload) VALUES (?,?,?)",
                       (result_id, identifier, payload))
            stored = db.execute("SELECT id,payload FROM arena_results WHERE experiment_id=?", (identifier,)).fetchone()
            if stored["id"] != result_id or stored["payload"] != payload:
                raise ArenaError("ARENA_REPLAY_MISMATCH: resultado anterior preservado")
        return {"id": result_id, **result}

    def _aggregate(self, experiment: dict, run_ids: dict) -> dict:
        config = ArenaConfig.model_validate(experiment["config"])
        ids = ProtocolIds.model_validate(experiment["protocol_ids"])
        protocols = self._check_protocols(config, ids)
        if set(run_ids) != set(PARTITIONS) or any(set(run_ids[p]) != set(STRATEGIES) for p in PARTITIONS):
            raise ArenaError("ARENA_RUN_SET_INVALID")
        windows = {"train": (config.train_start, config.train_end), "validation": (config.train_end, config.validation_end),
                   "test": (config.validation_end, config.test_end)}
        rankings = {}
        for partition in PARTITIONS:
            results = {strategy: self.research.result(run_ids[partition][strategy]) for strategy in STRATEGIES}
            benchmark = results["buy_hold"]["simulation"]
            entries = []
            for strategy in STRATEGIES:
                result, protocol = results[strategy], protocols[strategy]
                manifest, simulation = result["manifest"], result["simulation"]
                if (manifest["dataset_hash"] != config.dataset_hash or manifest["symbol"] != config.symbol
                    or manifest["interval"] != config.interval or (manifest["start_time"], manifest["end_time"]) != windows[partition]
                    or manifest["partition"] != partition or manifest["strategy"] != strategy
                    or manifest["strategy_version"] != getattr(config.strategies, strategy).version
                    or manifest["protocol_id"] != getattr(ids, strategy)
                    or manifest["parameters"] != getattr(config.strategies, strategy).parameters.model_dump(mode="json")
                    or manifest["config"] != config.backtest.model_dump(mode="json")
                    or manifest["instrument"] != protocol["instrument"]
                    or manifest["code_hash"] != protocol["code_hash"] or manifest["engine_version"] != protocol["engine_version"]
                    or Decimal(simulation["equity"][0]["equity"]) != config.backtest.capital
                    or Decimal(simulation["equity"][0]["cash"]) != config.backtest.capital
                    or Decimal(simulation["equity"][0]["quantity"]) != 0
                    or result["benchmark"] != benchmark):
                    raise ArenaError("ARENA_INCOMPARABLE_RUNS")
                m = simulation["metrics"]
                with localcontext() as ctx:
                    ctx.prec = 34
                    excess = Decimal(m["net_return_pct"]) - Decimal(benchmark["metrics"]["net_return_pct"])
                if Decimal(result["excess_return_pp"]) != excess:
                    raise ArenaError("ARENA_BENCHMARK_MISMATCH")
                entries.append({"strategy": strategy, "strategy_version": manifest["strategy_version"],
                    "parameters": manifest["parameters"], "protocol_id": manifest["protocol_id"], "run_id": result["id"],
                    "net_return_pct": m["net_return_pct"], "max_drawdown_pct": m["max_drawdown_pct"],
                    "profit_factor": m["profit_factor"], "win_rate_pct": m["win_rate_pct"],
                    "closed_trades": m["closed_trades"], "expectancy": m["expectancy"], "total_costs": m["total_costs"],
                    "exposure_pct": m["exposure_pct"], "excess_return_pp": str(excess),
                    "undefined": m["undefined"], "insufficient_sample": m["closed_trades"] < 30})
            entries = rank_entries(entries)
            rankings[partition] = {"start_time": windows[partition][0], "end_time": windows[partition][1],
                "out_of_sample": partition == "test", "entries": entries,
                "insufficient_sample": any(e["insufficient_sample"] for e in entries), "validated_winner": None}
        return {"arena_version": ARENA_VERSION, "experiment_id": experiment["id"], "run_ids": run_ids,
                "rankings": rankings, "warnings": ["Ranking descritivo; desempenho histórico não prevê resultados futuros.",
                "Menos de 30 trades indica amostra insuficiente; 30 trades não validam uma estratégia.",
                "Buy & Hold não usa stop; exposição e risco realizados podem diferir entre estratégias."]}

    def result(self, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute("SELECT id,payload FROM arena_results WHERE experiment_id=?", (identifier,)).fetchone()
        if not row:
            raise ArenaError("ARENA_RESULT_NOT_FOUND")
        if hashlib.sha256(row["payload"].encode("utf-8")).hexdigest() != row["id"]:
            raise ArenaError("ARENA_RESULT_HASH_MISMATCH")
        value = json.loads(row["payload"])
        exp = self.experiment(identifier)
        if self._aggregate(exp, value["run_ids"]) != value:
            raise ArenaError("ARENA_RESULT_INTEGRITY_ERROR")
        return {"id": row["id"], **value}
