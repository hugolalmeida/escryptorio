"""Contratos explícitos para análise virtual; valores financeiros nunca usam float."""
from decimal import Decimal
from pydantic import Field, model_validator

from cryptolab.engine.contracts import Contract, CostModel


def reject_float(value):
    if isinstance(value, float):
        raise ValueError("Valores financeiros devem ser strings ou Decimal")
    if isinstance(value, dict):
        for item in value.values():
            reject_float(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            reject_float(item)


class RiskPolicy(Contract):
    risk_fraction: Decimal = Field(gt=0, le=1, max_digits=28, decimal_places=18)
    exposure_fraction: Decimal = Field(gt=0, le=1, max_digits=28, decimal_places=18)
    costs: CostModel

    @model_validator(mode="before")
    @classmethod
    def no_floats_or_default_costs(cls, value):
        reject_float(value)
        if not isinstance(value, dict) or not isinstance(value.get("costs"), dict) or set(value["costs"]) != {"fee_rate", "slippage_rate"}:
            raise ValueError("Taxa e slippage virtuais devem ser explícitos")
        for raw in value["costs"].values():
            try:
                number = Decimal(str(raw))
                if not number.is_finite() or len(number.as_tuple().digits) > 28 or number.as_tuple().exponent < -18:
                    raise ValueError()
            except ArithmeticError:
                raise ValueError("Precisão de custo inválida") from None
        return value


class PlannerBinding(Contract):
    schema_version: int = Field(default=1, ge=1, le=1)
    wallet_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    wallet_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    monitor_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    risk: RiskPolicy

    @model_validator(mode="before")
    @classmethod
    def no_floats(cls, value):
        reject_float(value)
        return value
