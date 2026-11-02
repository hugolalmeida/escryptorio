"""Deterministic OHLC replay. This module cannot access storage, SDKs or HTTP."""
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR, localcontext

from cryptolab.engine.contracts import (BacktestConfig, BacktestMetrics, EquityPoint, Fill,
    InstrumentRules, OrderIntent, Portfolio, Position, SignalPlan, Simulation, StrategyId,
    StrategyParameters, Trade)
from cryptolab.engine.strategies import ResearchStrategy, warmup
from cryptolab.models import Candle


def rounded(value: D, step: D, up: bool = False) -> D:
    return (value/step).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*step


def execution_price(reference: D, side: str, config: BacktestConfig, rules: InstrumentRules) -> D:
    return rounded(reference*(1+config.costs.slippage_rate if side == "buy" else 1-config.costs.slippage_rate),
                   rules.price_tick, side == "buy")


def metrics(capital: D, equity: list[EquityPoint], trades: list[Trade], fills: list[Fill], exposed: int) -> BacktestMetrics:
    with localcontext() as ctx:
        ctx.prec = 34
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [-t.pnl for t in trades if t.pnl < 0]
        gross_gain, gross_loss = sum(wins, D(0)), sum(losses, D(0))
        fees = sum((f.fee for f in fills), D(0))
        slip = sum((f.slippage_cost for f in fills), D(0))
        undefined = {}
        if not trades:
            undefined.update(win_rate_pct="Sem trades encerrados", expectancy="Sem trades encerrados")
        if not losses:
            undefined["profit_factor"] = "Sem perdas realizadas; denominador zero"
        if not wins or not losses:
            undefined["realized_win_loss_ratio"] = "Exige ao menos um ganho e uma perda"
        return BacktestMetrics(net_return_pct=(equity[-1].equity/capital-1)*100,
            pnl=equity[-1].equity-capital, final_equity=equity[-1].equity,
            max_drawdown_pct=max(e.drawdown_pct for e in equity),
            win_rate_pct=D(len(wins))/len(trades)*100 if trades else None,
            profit_factor=gross_gain/gross_loss if losses else None,
            expectancy=sum((t.pnl for t in trades), D(0))/len(trades) if trades else None,
            closed_trades=len(trades), wins=len(wins), losses=len(losses),
            breakeven=len(trades)-len(wins)-len(losses),
            realized_win_loss_ratio=(gross_gain/len(wins))/(gross_loss/len(losses)) if wins and losses else None,
            fees=fees, slippage_cost=slip, total_costs=fees+slip,
            exposure_pct=D(exposed)/(len(equity)-1)*100, undefined=undefined)


def simulate(candles: tuple[Candle, ...], step: int, start: int, end: int, strategy: StrategyId,
             parameters: StrategyParameters, config: BacktestConfig, rules: InstrumentRules) -> Simulation:
    # Validate even direct pure-engine calls. Production supplies DatasetReader output only.
    if (step <= 0 or start % step or end % step or end <= start or not candles
            or len(candles) > 100_000 or any(not c.closed or c.time % step for c in candles)
            or any(b.time-a.time != step for a, b in zip(candles, candles[1:]))
            or start < candles[0].time or end > candles[-1].time+step):
        raise ValueError("Candles fechados, contíguos e recorte alinhado obrigatórios")
    first = (start-candles[0].time)//step
    last = (end-candles[0].time)//step
    if first+1 < warmup(strategy, parameters) or last-first < 2:
        raise ValueError("Warm-up insuficiente ou menos de dois candles no recorte")
    # Trim future candles before feature computation; prefix invariance tested separately.
    candles = candles[:last]
    with localcontext() as ctx:
        ctx.prec = 34
        logic = ResearchStrategy(strategy, parameters, candles)
        cash, peak = config.capital, config.capital
        position = None
        pending = None
        attempted_benchmark = False
        fills, trades, plans, rejections = [], [], [], []
        equity = [EquityPoint(time=start, equity=cash, cash=cash, quantity=D(0), drawdown_pct=D(0))]
        exposed = 0

        def sell(reference: D, stamp: int, candle_time: int, reason: str, decision_time: int | None = None):
            nonlocal cash, position
            price = execution_price(reference, "sell", config, rules)
            quantity = position.quantity
            notional = quantity*price
            if (price <= 0 or notional < rules.min_notional or quantity < rules.min_quantity
                    or (rules.max_notional is not None and notional > rules.max_notional) or quantity > rules.max_quantity):
                rejections.append(f"{candle_time}: saída {reason} recusada por limites; posição permanece aberta")
                return
            fee = notional*config.costs.fee_rate
            cash += notional-fee
            fill = Fill(side="sell", time=stamp, candle_time=candle_time, decision_time=decision_time,
                price=price, reference_price=reference, quantity=quantity, fee=fee,
                slippage_cost=(reference-price)*quantity, reason=reason, cash_after=cash)
            entry_cost = position.entry.quantity*position.entry.price+position.entry.fee
            pnl = notional-fee-entry_cost
            trades.append(Trade(entry=position.entry, exit=fill, pnl=pnl, return_pct=pnl/entry_cost*100,
                                planned_stop=position.stop, planned_target=position.target))
            fills.append(fill)
            position = None

        for i in range(first, last):
            c = candles[i]
            was_exposed = False
            if pending:
                intent = pending
                pending = None
                if intent.plan.valid_at_open != c.time:
                    raise ValueError("Intenção fora da validade")
                if intent.side == "sell" and position:
                    sell(c.open, c.time, c.time, intent.plan.reason, intent.plan.decision_time)
                elif intent.side == "buy" and position is None:
                    price = execution_price(c.open, "buy", config, rules)
                    stop = rounded(price*(1-parameters.stop_fraction), rules.price_tick) if strategy != "buy_hold" else None
                    target = rounded(price*(1+parameters.target_fraction), rules.price_tick, True) if stop is not None else None
                    budget = min(cash/(1+config.costs.fee_rate), cash*config.exposure_fraction)
                    if rules.max_notional is not None:
                        budget = min(budget, rules.max_notional)
                    quantity = min(budget/price, rules.max_quantity)
                    if stop is not None:
                        stop_fill = execution_price(stop, "sell", config, rules)
                        planned_loss = price*(1+config.costs.fee_rate)-stop_fill*(1-config.costs.fee_rate)
                        quantity = min(quantity, cash*config.risk_fraction/planned_loss)
                    quantity = rounded(quantity, rules.quantity_step)
                    notional = price*quantity
                    fee = notional*config.costs.fee_rate
                    if (quantity <= 0 or quantity < rules.min_quantity or notional < rules.min_notional
                            or notional+fee > cash or (stop is not None and stop <= 0)):
                        rejections.append(f"{c.time}: entrada recusada por saldo, risco ou mínimos")
                    else:
                        cash -= notional+fee
                        fill = Fill(side="buy", time=c.time, candle_time=c.time, decision_time=intent.plan.decision_time,
                            price=price, reference_price=c.open, quantity=quantity, fee=fee,
                            slippage_cost=(price-c.open)*quantity, reason=intent.plan.reason, cash_after=cash)
                        fills.append(fill)
                        position = Position(quantity=quantity, entry=fill, stop=stop, target=target)
                        was_exposed = True
            was_exposed = was_exposed or position is not None
            if position and position.stop is not None:
                # Entry happened at this open; same-bar protection is permitted after entry.
                if c.open <= position.stop:
                    sell(c.open, c.time, c.time, "stop_gap")
                elif c.open >= position.target:
                    sell(c.open, c.time, c.time, "target_gap")
                elif c.low <= position.stop:
                    sell(position.stop, c.time+step, c.time, "stop_intrabar")
                elif c.high >= position.target:
                    sell(position.target, c.time+step, c.time, "target_intrabar")
            exposed += int(was_exposed)
            if i == last-1 and position and config.final_policy == "liquidate":
                sell(c.close, end, c.time, "final_liquidation")
            quantity = position.quantity if position else D(0)
            marked = cash+quantity*c.close
            peak = max(peak, marked)
            equity.append(EquityPoint(time=c.time+step, equity=marked, cash=cash, quantity=quantity,
                                      drawdown_pct=(peak-marked)/peak*100))
            if cash < 0:
                raise ArithmeticError("Invariante de saldo violada")
            if i == last-1:
                continue
            decision = logic.decide(i, position is not None)
            if strategy == "buy_hold" and attempted_benchmark:
                continue
            if decision.action != "hold":
                plan = SignalPlan(decision_time=c.time+step, valid_at_open=c.time+step, reference_price=c.close,
                    planned_stop=c.close*(1-parameters.stop_fraction) if strategy != "buy_hold" else None,
                    planned_target=c.close*(1+parameters.target_fraction) if strategy != "buy_hold" else None,
                    reward_risk=parameters.target_fraction/parameters.stop_fraction if strategy != "buy_hold" else None,
                    reason=decision.reason)
                plans.append(plan)
                pending = OrderIntent(side=decision.action, plan=plan)
                if strategy == "buy_hold":
                    attempted_benchmark = True
        return Simulation(metrics=metrics(config.capital, equity, trades, fills, exposed), equity=tuple(equity),
            fills=tuple(fills), trades=tuple(trades), plans=tuple(plans), rejections=tuple(rejections),
            portfolio=Portfolio(cash=cash, position=position))
