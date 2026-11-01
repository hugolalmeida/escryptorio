from decimal import Decimal as D, getcontext

import pytest

from cryptolab.engine.indicators import atr, calculate, ema, rsi, sma


def test_sma_and_ema_reference():
    values = list(map(D, [1, 2, 3, 4, 5]))
    assert sma(values, 3) == [None, None, D(2), D(3), D(4)]
    assert ema(values, 3) == [None, None, D(2), D(3), D(4)]
    assert ema([D(10), D(10), D(10), D(20)], 3)[-1] == D(15)


def test_wilder_rsi_reference():
    # Série de referência publicada por J. Welles Wilder, com semente média simples.
    values = list(map(D, ["44.34", "44.09", "44.15", "43.61", "44.33", "44.83", "45.10", "45.42",
                          "45.84", "46.08", "45.89", "46.03", "45.61", "46.28", "46.28", "46.00"]))
    result = rsi(values)
    assert all(v is None for v in result[:14])
    assert abs(result[14] - D("70.464135021097")) < D("0.00000001")
    assert abs(result[15] - D("66.249618553555")) < D("0.00000001")


def test_rsi_limits_and_flat_market():
    assert rsi(list(map(D, range(1, 25))))[-1] == 100
    assert rsi(list(map(D, range(25, 1, -1))))[-1] == 0
    assert rsi([D(42)] * 20)[-1] == 50


def test_warmup_and_invalid_periods():
    assert calculate([]).trend == "insuficiente"
    assert atr([], 14) is None
    assert sma([D(1)], 2) == [None]
    assert ema([D(1)], 2) == [None]
    assert rsi([D(1)] * 14)[-1] is None
    for fn in (sma, ema, rsi, atr):
        with pytest.raises(ValueError):
            fn([], 0)


def test_atr_includes_gaps(candles):
    assert atr(candles, 14) == D(3)
    modified = candles[:14] + [candles[14].model_copy(update={"open": D(130), "high": D(132), "low": D(129), "close": D(131)})]
    # previous close=114; true range=max(3,18,15)=18
    assert abs(atr(modified) - D(57) / 14) < D("1e-25")


def test_prefix_invariance():
    values = [D(100) + D(i % 7) - D(i % 3) for i in range(100)]
    for fn in (sma, ema, rsi):
        full = fn(values, 14)
        for end in (15, 21, 50, 80):
            assert full[:end] == fn(values[:end], 14)


def test_open_candle_cannot_change_indicators(candles):
    expected = calculate(candles)
    open_candle = candles[-1].model_copy(update={"time": candles[-1].time + 3600, "closed": False,
                                              "high": D(999999), "close": D(999999)})
    assert calculate(candles + [open_candle]) == expected


def test_independent_of_global_decimal_context(candles):
    reference = calculate(candles)
    previous = getcontext().prec
    try:
        getcontext().prec = 6
        assert calculate(candles) == reference
    finally:
        getcontext().prec = previous


def test_reject_out_of_order(candles):
    with pytest.raises(ValueError):
        calculate(list(reversed(candles)))
    with pytest.raises(ValueError):
        calculate(candles + [candles[-1]])
    with pytest.raises(ValueError):
        calculate(candles[:10] + candles[11:])
