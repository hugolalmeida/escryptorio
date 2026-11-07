"""Transições puras de eventos virtuais, sem relógio, rede ou persistência."""
from decimal import Context, Decimal as D, ROUND_HALF_EVEN, localcontext

from cryptolab.config import INTERVALS
from cryptolab.paper.models import FillRecord, MarkRecord, StateRecord, WalletSpec, WalletState

PRECISION = 80
LEDGER_VERSION = "cryptolab-paper-ledger/1"
LEDGER_CONTEXT = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)


def initial_state(spec: WalletSpec) -> WalletState:
    return WalletState(cash=spec.initial_capital, quantity=D(0), acquisition_cost=D(0),
        realized_pnl=D(0), total_fees=D(0), state="paused", mark_price=None,
        mark_candle_time=None, mark_event_time=None, last_event_time=spec.opened_at)


def apply(state: WalletState, spec: WalletSpec, kind: str, value: dict) -> WalletState:
    with localcontext(LEDGER_CONTEXT):
        if kind == "state":
            record = StateRecord.model_validate(value)
        elif kind == "fill":
            record = FillRecord.model_validate(value)
        elif kind == "mark":
            record = MarkRecord.model_validate(value)
        else:
            raise ValueError("Tipo de evento não suportado")
        if record.event_time < state.last_event_time:
            raise ValueError("Eventos devem respeitar a ordem temporal")
        if kind in ("fill", "mark") and (record.candle_time % INTERVALS[spec.interval] or record.event_time < record.candle_time):
            raise ValueError("Referência de candle desalinhada ou posterior ao evento")
        if kind == "state":
            if record.state == state.state:
                raise ValueError("Estado operacional já está definido")
            return state.model_copy(update={"state":record.state,"last_event_time":record.event_time})
        if kind == "mark":
            if state.mark_candle_time is not None and record.candle_time < state.mark_candle_time:
                raise ValueError("Marcação não pode regredir no tempo")
            return state.model_copy(update={"mark_price":record.price,"mark_candle_time":record.candle_time,
                "mark_event_time":record.event_time,"last_event_time":record.event_time})
        if state.state != "active":
            raise ValueError("Carteira pausada não aceita fill virtual")
        notional = record.quantity * record.price
        if record.side == "buy":
            amount = notional + record.fee
            if amount > state.cash:
                raise ValueError("Saldo insuficiente; margem proibida")
            return state.model_copy(update={"cash":state.cash-amount, "quantity":state.quantity+record.quantity,
                "acquisition_cost":state.acquisition_cost+amount, "total_fees":state.total_fees+record.fee,
                "last_event_time":record.event_time})
        if record.quantity > state.quantity:
            raise ValueError("Quantidade insuficiente; short proibido")
        proceeds = notional-record.fee
        if proceeds < 0:
            raise ValueError("Taxa superior ao valor da venda")
        cost = state.acquisition_cost if record.quantity == state.quantity else state.acquisition_cost*record.quantity/state.quantity
        return state.model_copy(update={"cash":state.cash+proceeds, "quantity":state.quantity-record.quantity,
            "acquisition_cost":state.acquisition_cost-cost, "realized_pnl":state.realized_pnl+proceeds-cost,
            "total_fees":state.total_fees+record.fee, "last_event_time":record.event_time})
