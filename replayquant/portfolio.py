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

    @property
    def asset_quantity(self):
        return self.btc


@dataclass(frozen=True)
class AssetBalance:
    cash: Decimal
    asset_quantity: Decimal = Decimal('0')

    def __post_init__(self):
        decimal_value(self.cash, 'cash', bounded=False)
        decimal_value(self.asset_quantity, 'asset_quantity', bounded=False)


@financial
def fill_movements(fill: Fill):
    """Bruto e deltas comuns aos livros individual e compartilhado."""
    if not isinstance(fill, Fill):
        raise ValidationError('Preenchimento inválido')
    gross = fill.price * fill.quantity
    buy = fill.side == 'BUY'
    return gross, -(gross + fill.fee) if buy else gross - fill.fee, fill.quantity if buy else -fill.quantity


@financial
def after_fill(balance: Balance, fill: Fill):
    if not isinstance(balance, (Balance, AssetBalance)) or not isinstance(fill, Fill):
        raise ValidationError("Saldo e preenchimento inválidos")
    gross, cash_delta, asset_delta = fill_movements(fill)
    if fill.side == "BUY":
        if balance.asset_quantity != 0:
            raise ValidationError("POSITION_OPEN")
        if balance.cash < gross + fill.fee:
            raise ValidationError("INSUFFICIENT_CASH")
        return type(balance)(balance.cash + cash_delta, balance.asset_quantity + asset_delta)
    if balance.asset_quantity < fill.quantity:
        raise ValidationError("INSUFFICIENT_ASSET")
    return type(balance)(balance.cash + cash_delta, balance.asset_quantity + asset_delta)
