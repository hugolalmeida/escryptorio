from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from cryptolab.engine.contracts import Contract
from cryptolab.models import Interval, Symbol

Money = Decimal
Key = str


class PaperContract(Contract):
    @model_validator(mode="before")
    @classmethod
    def no_binary_floats(cls, value):
        if isinstance(value, dict) and any(isinstance(item, float) for item in value.values()):
            raise ValueError("Valores financeiros devem ser strings ou Decimal, nunca float")
        return value


class WalletSpec(PaperContract):
    bot_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    strategy: Literal["trend", "rsi", "breakout", "buy_hold"]
    strategy_version: Literal["1"] = "1"
    symbol: Symbol
    interval: Interval
    initial_capital: Money = Field(gt=0, max_digits=28, decimal_places=18)
    opened_at: int = Field(ge=0)


class FillRecord(PaperContract):
    """Registro explícito de fill virtual externo, nunca uma ordem à corretora."""
    side: Literal["buy", "sell"]
    quantity: Money = Field(gt=0, max_digits=28, decimal_places=18)
    price: Money = Field(gt=0, max_digits=28, decimal_places=18)
    fee: Money = Field(ge=0, max_digits=28, decimal_places=18)
    reference_price: Money = Field(gt=0, max_digits=28, decimal_places=18)
    candle_time: int = Field(ge=0)
    event_time: int = Field(ge=0)


class MarkRecord(PaperContract):
    price: Money = Field(gt=0, max_digits=28, decimal_places=18)
    candle_time: int = Field(ge=0)
    event_time: int = Field(ge=0)


class StateRecord(PaperContract):
    state: Literal["active", "paused"]
    event_time: int = Field(ge=0)


class WalletState(PaperContract):
    cash: Money
    quantity: Money
    acquisition_cost: Money
    realized_pnl: Money
    total_fees: Money
    state: Literal["active", "paused"]
    mark_price: Money | None
    mark_candle_time: int | None
    mark_event_time: int | None
    last_event_time: int

    @property
    def equity(self) -> Money | None:
        if self.quantity == 0:
            return self.cash
        if self.mark_price is None:
            return None
        # Caller performs this under the ledger's deterministic Decimal context.
        return self.cash + self.quantity*self.mark_price
