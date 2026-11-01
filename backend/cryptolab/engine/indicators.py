from decimal import Decimal, localcontext

from cryptolab.models import Candle, IndicatorPoint, Indicators

D = Decimal


def sma(values: list[Decimal], period: int) -> list[Decimal | None]:
    if period < 1:
        raise ValueError("Período deve ser positivo")
    with localcontext() as ctx:
        ctx.prec = 34
        return [None if i + 1 < period else sum(values[i + 1 - period:i + 1], D(0)) / period
                for i in range(len(values))]


def ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    if period < 1:
        raise ValueError("Período deve ser positivo")
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result
    with localcontext() as ctx:
        ctx.prec = 34
        current = sum(values[:period], D(0)) / period
        result[period - 1] = current
        alpha = D(2) / (period + 1)
        for i in range(period, len(values)):
            current = values[i] * alpha + current * (1 - alpha)
            result[i] = current
    return result


def rsi(values: list[Decimal], period: int = 14) -> list[Decimal | None]:
    if period < 1:
        raise ValueError("Período deve ser positivo")
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= period:
        return result
    with localcontext() as ctx:
        ctx.prec = 34
        changes = [b - a for a, b in zip(values, values[1:])]
        gains = [max(d, D(0)) for d in changes]
        losses = [max(-d, D(0)) for d in changes]
        gain, loss = sum(gains[:period], D(0)) / period, sum(losses[:period], D(0)) / period

        def value():
            if gain == loss == 0:
                return D(50)
            return D(100) if loss == 0 else D(100) - D(100) / (1 + gain / loss)

        result[period] = value()
        for i in range(period, len(changes)):
            gain = (gain * (period - 1) + gains[i]) / period
            loss = (loss * (period - 1) + losses[i]) / period
            result[i + 1] = value()
    return result


def atr(candles: list[Candle], period: int = 14) -> Decimal | None:
    if period < 1:
        raise ValueError("Período deve ser positivo")
    if len(candles) < period:
        return None
    with localcontext() as ctx:
        ctx.prec = 34
        ranges = [c.high - c.low if i == 0 else max(c.high - c.low, abs(c.high - candles[i-1].close),
                  abs(c.low - candles[i-1].close)) for i, c in enumerate(candles)]
        current = sum(ranges[:period], D(0)) / period
        for v in ranges[period:]:
            current = (current * (period - 1) + v) / period
        return current


def calculate(candles: list[Candle]) -> Indicators:
    if any(b.time <= a.time for a, b in zip(candles, candles[1:])):
        raise ValueError("Candles devem estar em ordem estrita e sem duplicatas")
    if len(candles) > 2:
        step = candles[1].time - candles[0].time
        if any(b.time - a.time != step for a, b in zip(candles, candles[1:])):
            raise ValueError("Candles devem ser contíguos")
    if any(not a.closed and b.closed for a, b in zip(candles, candles[1:])):
        raise ValueError("Candle aberto deve estar no final")
    closed = [c for c in candles if c.closed]
    values = [c.close for c in closed]
    smas, emas = sma(values, 20), ema(values, 50)
    trend = "insuficiente"
    if values and emas[-1] is not None:
        trend = "alta" if values[-1] > smas[-1] > emas[-1] else (
            "baixa" if values[-1] < smas[-1] < emas[-1] else "neutra")
    return Indicators(
        sma_20=[IndicatorPoint(time=c.time, value=v) for c, v in zip(closed, smas) if v is not None],
        ema_50=[IndicatorPoint(time=c.time, value=v) for c, v in zip(closed, emas) if v is not None],
        rsi_14=rsi(values)[-1] if values else None,
        atr_14=atr(closed), trend=trend, as_of=closed[-1].time if closed else None,
        closed_candles=len(closed),
    )
