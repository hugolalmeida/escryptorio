"""Causal feature series. Each decision reads only its own and previous feature row."""
from decimal import Decimal as D, localcontext

from cryptolab.engine.contracts import Decision, StrategyId, StrategyParameters
from cryptolab.engine.indicators import sma, rsi, atr
from cryptolab.models import Candle


def warmup(strategy: StrategyId, p: StrategyParameters) -> int:
    if strategy == "trend":
        return max(p.slow + 1, 14 if p.max_atr_ratio is not None else 0)
    if strategy == "rsi":
        return max(p.rsi_period + 2, p.slow if p.trend_filter else 0)
    return p.lookback + 1 if strategy == "breakout" else 1


class ResearchStrategy:
    version = "1"

    def __init__(self, identifier: StrategyId, p: StrategyParameters, candles: tuple[Candle, ...]):
        self.identifier, self.parameters = identifier, p
        if identifier not in ("trend", "rsi", "breakout", "buy_hold"):
            raise ValueError("Estratégia indisponível; Mack não validada")
        # Store decisions as immutable per-candle facts, never pass a future window to decide.
        with localcontext() as ctx:
            ctx.prec = 34
            values = [c.close for c in candles]
            fast = sma(values, p.fast) if identifier == "trend" else []
            slow = sma(values, p.slow) if identifier == "trend" or (identifier == "rsi" and p.trend_filter) else []
            rsis = rsi(values, p.rsi_period) if identifier == "rsi" else []
            rows = []
            atr_value = None
            for i, c in enumerate(candles):
                enter = leave = False
                if p.max_atr_ratio is not None and identifier == "trend":
                    if i == 13:
                        atr_value = atr(list(candles[:14]))
                    elif i > 13:
                        tr = max(c.high-c.low, abs(c.high-candles[i-1].close), abs(c.low-candles[i-1].close))
                        atr_value = (atr_value*13 + tr)/14
                if i+1 >= warmup(identifier, p):
                    if identifier == "trend":
                        enter = fast[i] > slow[i] and c.close > fast[i]
                        if p.trend_entry == "cross":
                            enter = enter and fast[i-1] <= slow[i-1]
                        if p.max_atr_ratio is not None:
                            enter = enter and atr_value/c.close <= p.max_atr_ratio
                        leave = fast[i] <= slow[i] if p.trend_exit == "averages" else c.close < fast[i]
                    elif identifier == "rsi":
                        enter = rsis[i-1] <= p.rsi_entry < rsis[i]
                        if p.trend_filter:
                            enter = enter and c.close > slow[i]
                        leave = rsis[i] >= p.rsi_exit
                    elif identifier == "breakout":
                        previous = candles[i-p.lookback:i]
                        enter = c.close > max(x.high for x in previous)
                        if p.volume_multiple is not None:
                            enter = enter and c.volume >= sum((x.volume for x in previous), D(0))/p.lookback*p.volume_multiple
                        leave = c.close < min(x.low for x in previous)
                    else:
                        enter = True
                rows.append((enter, leave))
            self.rows = tuple(rows)

    def decide(self, index: int, in_position: bool) -> Decision:
        enter, leave = self.rows[index]
        if in_position and leave:
            return Decision(action="sell", reason={
                "trend": "SMA rápida <= lenta" if self.parameters.trend_exit == "averages" else "Fechamento < SMA rápida",
                "rsi": "RSI Wilder >= limiar configurado de saída",
                "breakout": "Fechamento < mínima dos N candles estritamente anteriores",
            }[self.identifier])
        if not in_position and enter:
            return Decision(action="buy", reason={
                "trend": "SMA rápida acima da lenta, confirmação de preço e filtros configurados",
                "rsi": "RSI Wilder recuperou o limiar de entrada de baixo para cima",
                "breakout": "Fechamento acima da máxima dos N candles anteriores e filtro de volume",
                "buy_hold": "Compra única do benchmark no primeiro fechamento elegível",
            }[self.identifier])
        return Decision(action="hold", reason="Sem condição de mudança de posição")
