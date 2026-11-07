from typing import Literal

from pydantic import Field

from cryptolab.engine.contracts import Contract, StrategyId, StrategyParameters
from cryptolab.models import Interval, Symbol


class MonitorConfig(Contract):
    bot_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    symbol: Symbol
    interval: Interval
    strategy: StrategyId
    strategy_version: Literal["1"] = "1"
    parameters: StrategyParameters = StrategyParameters()
