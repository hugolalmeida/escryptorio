from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Symbol = Literal["BTCUSDT", "ETHUSDT"]
Interval = Literal["15", "60", "240", "D"]


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    time: int = Field(ge=0)  # UTC seconds, candle open
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    turnover: Decimal = Field(ge=0)
    closed: bool

    @model_validator(mode="after")
    def valid_ohlc(self):
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("OHLC inválido")
        return self


class Ticker(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    symbol: Symbol
    price: Decimal = Field(gt=0)
    change_24h: Decimal
    high_24h: Decimal = Field(gt=0)
    low_24h: Decimal = Field(gt=0)
    volume_24h: Decimal = Field(ge=0)
    turnover_24h: Decimal = Field(ge=0)
    source_time_ms: int = Field(gt=0)


class IndicatorPoint(BaseModel):
    time: int
    value: Decimal


class Indicators(BaseModel):
    sma_20: list[IndicatorPoint]
    ema_50: list[IndicatorPoint]
    rsi_14: Decimal | None
    atr_14: Decimal | None
    trend: Literal["alta", "baixa", "neutra", "insuficiente"]
    as_of: int | None
    closed_candles: int


class Snapshot(BaseModel):
    schema_version: Literal[1] = 1
    source: Literal["Bybit"] = "Bybit"
    category: Literal["spot"] = "spot"
    symbol: Symbol
    interval: Interval
    fetched_at_ms: int
    source_time_ms: int
    ticker: Ticker
    candles: list[Candle]
    indicators: Indicators
    instrument: dict
    dataset_id: str
