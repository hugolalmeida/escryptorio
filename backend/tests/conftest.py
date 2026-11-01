import time
from decimal import Decimal as D

import pytest

from cryptolab.config import Settings
from cryptolab.engine.indicators import calculate
from cryptolab.models import Candle, Snapshot, Ticker
from cryptolab.storage import Store, canonical_dataset


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Testes unitários não podem acessar a rede")
    monkeypatch.setattr("requests.sessions.Session.request", blocked)


@pytest.fixture
def candles():
    # Fixture sintética e determinística, nunca servida pela aplicação.
    return [Candle(time=3600 * (i + 1), open=D(100 + i), high=D(102 + i), low=D(99 + i),
                   close=D(101 + i), volume=D(10), turnover=D(1000), closed=True) for i in range(80)]


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "test.sqlite3")


@pytest.fixture
def store(settings):
    result = Store(settings.database_path)
    result.migrate()
    return result


@pytest.fixture
def snapshot(candles):
    now = int(time.time() * 1000)
    ticker = Ticker(symbol="BTCUSDT", price=D("180.001"), change_24h=D("0.01"), high_24h=D(181),
                    low_24h=D(170), volume_24h=D(100), turnover_24h=D(18000), source_time_ms=now)
    return Snapshot(symbol="BTCUSDT", interval="60", fetched_at_ms=now, source_time_ms=now,
                    ticker=ticker, candles=candles, indicators=calculate(candles), instrument={},
                    dataset_id=canonical_dataset("BTCUSDT", "60", candles)[0])
