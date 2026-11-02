from typing import Literal

from pydantic import Field, model_validator

from cryptolab.engine.contracts import BacktestConfig, Contract, StrategyParameters
from cryptolab.models import Interval, Symbol

STRATEGIES = ("trend", "rsi", "breakout", "buy_hold")
PARTITIONS = ("train", "validation", "test")
ARENA_VERSION = "cryptolab-arena/1"


class StrategySpec(Contract):
    version: Literal["1"] = "1"
    parameters: StrategyParameters = StrategyParameters()


class StrategySet(Contract):
    trend: StrategySpec = StrategySpec()
    rsi: StrategySpec = StrategySpec()
    breakout: StrategySpec = StrategySpec()
    buy_hold: StrategySpec = StrategySpec()


class ProtocolIds(Contract):
    trend: str = Field(pattern=r"^[a-f0-9]{64}$")
    rsi: str = Field(pattern=r"^[a-f0-9]{64}$")
    breakout: str = Field(pattern=r"^[a-f0-9]{64}$")
    buy_hold: str = Field(pattern=r"^[a-f0-9]{64}$")


class ArenaConfig(Contract):
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    symbol: Symbol
    interval: Interval
    train_start: int = Field(ge=0)
    train_end: int = Field(ge=0)
    validation_end: int = Field(ge=0)
    test_end: int = Field(ge=0)
    backtest: BacktestConfig = BacktestConfig()
    strategies: StrategySet = StrategySet()
    # Optional explicit pre-existing protocols, including compatible legacy protocols.
    protocol_ids: ProtocolIds | None = None

    @model_validator(mode="after")
    def chronological(self):
        if not self.train_start < self.train_end < self.validation_end < self.test_end:
            raise ValueError("Janelas devem ser cronológicas e não sobrepostas")
        return self


class ArenaExperiment(Contract):
    arena_version: Literal["cryptolab-arena/1"] = ARENA_VERSION
    config: ArenaConfig
    protocol_ids: ProtocolIds


class ExecuteRequest(Contract):
    experiment_id: str = Field(pattern=r"^[a-f0-9]{64}$")
