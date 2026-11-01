import pytest

from cryptolab.bybit import MarketDataError, PublicBybit, validate_candles
from cryptolab.models import Candle
from cryptolab.worker import collect


def test_candle_integrity(candles):
    now = (candles[-1].time + 3600) * 1000
    validate_candles(candles, "60", now)
    for broken in ([], candles[::-1], candles + [candles[-1]], candles[:10] + candles[11:]):
        with pytest.raises(ValueError):
            validate_candles(broken, "60", now)
    with pytest.raises(ValueError):
        validate_candles(candles, "60", now + 90001)
    with pytest.raises(ValueError):
        validate_candles(candles, "60", candles[0].time * 1000)


def test_invalid_ohlc_and_nonfinite():
    base = dict(time=0, open="2", high="3", low="1", close="2", volume="0", turnover="0", closed=True)
    for change in ({"high": "1"}, {"low": "4"}, {"volume": "-1"}, {"close": "NaN"}, {"high": "Infinity"}):
        with pytest.raises(ValueError):
            Candle(**{**base, **change})


def test_only_public_spot_methods(monkeypatch):
    calls = []

    class FakeSDK:
        def __init__(self, **kwargs):
            assert not {"api_key", "api_secret"} & kwargs.keys()
            assert kwargs["testnet"] is False

        def get_tickers(self, **kwargs):
            calls.append(kwargs)
            return {"retCode": 0, "time": 1234, "result": {"category": "spot", "list": [{
                "symbol": "BTCUSDT", "lastPrice": "2.001", "price24hPcnt": "0.1", "highPrice24h": "3",
                "lowPrice24h": "1", "volume24h": "5", "turnover24h": "10"}]}}

        get_kline = get_tickers
        get_instruments_info = get_tickers

    monkeypatch.setattr("cryptolab.bybit.HTTP", FakeSDK)
    client = PublicBybit()
    assert str(client.ticker("BTCUSDT").price) == "2.001"
    assert calls == [{"category": "spot", "symbol": "BTCUSDT"}]
    for name, args in (("ticker", ("SOLUSDT",)), ("_read", ("order",))):
        with pytest.raises(MarketDataError):
            getattr(client, name)(*args)
    assert not hasattr(client, "place_order")


def test_upstream_error_is_sanitized(monkeypatch):
    class BrokenSDK:
        def __init__(self, **kwargs):
            pass

        def get_tickers(self, **kwargs):
            raise RuntimeError("secret or upstream payload")

        get_kline = get_tickers
        get_instruments_info = get_tickers

    monkeypatch.setattr("cryptolab.bybit.HTTP", BrokenSDK)
    with pytest.raises(MarketDataError, match="^BYBIT_UNAVAILABLE$"):
        PublicBybit().ticker("BTCUSDT")


def test_worker_failure_retains_data(store, snapshot):
    store.save(snapshot)

    class BrokenClient:
        def ticker(self, symbol):
            raise MarketDataError("BYBIT_UNAVAILABLE")

    assert collect(store, BrokenClient()) is False
    assert store.load("BTCUSDT", "60") == snapshot
    assert store.status()["error_code"] == "BYBIT_UNAVAILABLE"


@pytest.mark.parametrize("response", [
    {"retCode": 10006, "retMsg": "rate limit", "result": {}},
    {"retCode": 0, "result": {"category": "linear", "list": []}},
    {"retCode": 0, "time": 10, "result": {"category": "spot", "list": []}},
    {"retCode": 0, "time": 10, "result": {"category": "spot", "list": [{"symbol": "ETHUSDT"}]}},
])
def test_reject_bad_upstream_responses(monkeypatch, response):
    class FakeSDK:
        def __init__(self, **kwargs):
            pass

        def get_tickers(self, **kwargs):
            return response

        get_kline = get_tickers
        get_instruments_info = get_tickers

    monkeypatch.setattr("cryptolab.bybit.HTTP", FakeSDK)
    with pytest.raises(MarketDataError):
        PublicBybit().ticker("BTCUSDT")
