"""Saldos imutáveis e cálculo integral antes de qualquer transição do motor."""
from dataclasses import dataclass
from decimal import Decimal
from .models import Fill
from .validation import ValidationError, decimal_value, financial


@dataclass(frozen=True)
class Balance:
    cash: Decimal
    btc: Decimal = Decimal("0")

    def __post_init__(self):
        decimal_value(self.cash, "cash", bounded=False)
        decimal_value(self.btc, "btc", bounded=False)


@financial
def after_fill(balance: Balance, fill: Fill):
    if not isinstance(balance, Balance) or not isinstance(fill, Fill):
        raise ValidationError("Saldo e preenchimento inválidos")
    gross = fill.price * fill.quantity
    if fill.side == "BUY":
        if balance.btc != 0:
            raise ValidationError("POSITION_OPEN")
        if balance.cash < gross + fill.fee:
            raise ValidationError("INSUFFICIENT_CASH")
        return Balance(balance.cash - (gross + fill.fee), balance.btc + fill.quantity)
    if balance.btc < fill.quantity:
        raise ValidationError("INSUFFICIENT_ASSET")
    return Balance(balance.cash + (gross - fill.fee), balance.btc - fill.quantity)
