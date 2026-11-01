import logging
import time

from pybit.unified_trading import HTTP

from cryptolab.config import INTERVALS, SYMBOLS
from cryptolab.engine.indicators import calculate
from cryptolab.models import Candle, Snapshot, Ticker
from cryptolab.storage import canonical_dataset


class MarketDataError(Exception):
    """Erro sanitizado: não inclui resposta, URL, headers ou credenciais."""


class PublicBybit:
    """Única fronteira com a corretora. Apenas três métodos GET públicos."""

    def __init__(self):
        logging.getLogger("pybit").setLevel(logging.CRITICAL)
        self.__session = HTTP(testnet=False, timeout=6, max_retries=2, retry_delay=1,
                              force_retry=False, log_requests=False)

    def _read(self, resource: str, **params) -> dict:
        readers = {"ticker": self.__session.get_tickers, "candles": self.__session.get_kline,
                   "instrument": self.__session.get_instruments_info}
        if params.get("symbol") not in SYMBOLS or resource not in readers:
            raise MarketDataError("UNSUPPORTED_MARKET")
        try:
            result = readers[resource](category="spot", **params)
            if result.get("retCode") != 0 or result["result"].get("category") != "spot":
                raise MarketDataError("BYBIT_RESPONSE_ERROR")
            return result
        except MarketDataError:
            raise
        except Exception:
            raise MarketDataError("BYBIT_UNAVAILABLE") from None

    def ticker(self, symbol: str) -> Ticker:
        response = self._read("ticker", symbol=symbol)
        try:
            row = response["result"]["list"][0]
            if row["symbol"] != symbol:
                raise ValueError("symbol")
            return Ticker(symbol=symbol, price=row["lastPrice"], change_24h=row["price24hPcnt"],
                          high_24h=row["highPrice24h"], low_24h=row["lowPrice24h"], volume_24h=row["volume24h"],
                          turnover_24h=row["turnover24h"], source_time_ms=int(response["time"]))
        except (KeyError, IndexError, ValueError, TypeError):
            raise MarketDataError("BYBIT_INVALID_DATA") from None

    def instrument(self, symbol: str) -> dict:
        response = self._read("instrument", symbol=symbol)
        try:
            row = response["result"]["list"][0]
            if row["symbol"] != symbol or row["status"] != "Trading":
                raise ValueError("instrument")
            return {"symbol": row["symbol"], "status": row["status"], "base_coin": row["baseCoin"],
                    "quote_coin": row["quoteCoin"], "price_filter": row["priceFilter"],
                    "lot_size_filter": row["lotSizeFilter"], "source_time_ms": int(response["time"])}
        except (KeyError, IndexError, ValueError, TypeError):
            raise MarketDataError("BYBIT_INVALID_INSTRUMENT") from None

    def snapshot(self, symbol: str, interval: str, ticker: Ticker, instrument: dict) -> Snapshot:
        if interval not in INTERVALS:
            raise MarketDataError("UNSUPPORTED_INTERVAL")
        response = self._read("candles", symbol=symbol, interval=interval, limit=300)
        try:
            now = int(response["time"])
            rows = response["result"]["list"]
            if response["result"]["symbol"] != symbol or not rows:
                raise ValueError("empty or wrong symbol")
            candles = [Candle(time=int(r[0]) // 1000, open=r[1], high=r[2], low=r[3], close=r[4],
                              volume=r[5], turnover=r[6], closed=int(r[0]) + INTERVALS[interval] * 1000 <= now)
                       for r in reversed(rows)]
            validate_candles(candles, interval, now)
            dataset_id, _ = canonical_dataset(symbol, interval, candles)
            return Snapshot(symbol=symbol, interval=interval, fetched_at_ms=int(time.time() * 1000),
                            source_time_ms=min(now, ticker.source_time_ms), ticker=ticker, candles=candles,
                            indicators=calculate(candles), instrument=instrument, dataset_id=dataset_id)
        except (KeyError, IndexError, ValueError, TypeError):
            raise MarketDataError("BYBIT_INVALID_CANDLES") from None


def validate_candles(candles: list[Candle], interval: str, source_time_ms: int):
    step = INTERVALS[interval]
    if not candles or any(b.time - a.time != step for a, b in zip(candles, candles[1:])):
        raise ValueError("Candles vazios, duplicados, fora de ordem ou com lacunas")
    if any(c.time % step != 0 for c in candles):
        raise ValueError("Abertura desalinhada")
    if candles[-1].time * 1000 > source_time_ms or source_time_ms - (candles[-1].time + step) * 1000 > 90000:
        raise ValueError("Candles antigos ou futuros")
