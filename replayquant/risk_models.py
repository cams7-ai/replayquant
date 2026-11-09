"""Contratos opt-in schema 4; entradas antigas continuam independentes."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .models import SMAParameters, instrument
from .validation import ValidationError, decimal_value, identifier, utc


@dataclass(frozen=True)
class InstrumentFilters:
    step: Decimal
    min_quantity: Decimal
    min_notional: Decimal

    def __post_init__(self):
        decimal_value(self.step, 'step', positive=True)
        decimal_value(self.min_quantity, 'min_quantity', positive=True)
        decimal_value(self.min_notional, 'min_notional')


@dataclass(frozen=True)
class RiskParameters:
    risk_fraction: Decimal
    exposure_fraction: Decimal
    stop_fraction: Decimal
    target_fraction: Decimal
    daily_loss_fraction: Decimal
    drawdown_fraction: Decimal
    max_price_age_seconds: Decimal

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = decimal_value(getattr(self, name), name, positive=True)
            if name != 'max_price_age_seconds' and (value > 1 or (name == 'stop_fraction' and value == 1)):
                raise ValidationError(f'{name}: fração fora da faixa permitida')


@dataclass(frozen=True)
class RiskRequest:
    id: str
    at_close: datetime
    side: str
    target_order_id: str | None = None

    def __post_init__(self):
        identifier(self.id)
        object.__setattr__(self, 'at_close', utc(self.at_close))
        if type(self.side) is not str or self.side not in ('BUY', 'SELL', 'CANCEL'):
            raise ValidationError('Ação de risco exige BUY, SELL ou CANCEL')
        if self.side == 'CANCEL':
            identifier(self.target_order_id, 'target_order_id')
        elif self.target_order_id is not None:
            raise ValidationError('BUY/SELL não aceitam target_order_id')


@dataclass(frozen=True)
class RiskConfig:
    mode: str
    source: str
    symbol: str
    interval: str
    initial_cash: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    instrument_filters: InstrumentFilters
    risk: RiskParameters
    orders: tuple[RiskRequest, ...] = ()
    strategy: SMAParameters | None = None

    def __post_init__(self):
        instrument(self.source, self.symbol, self.interval)
        if type(self.mode) is not str or self.mode not in ('MANUAL', 'SMA'):
            raise ValidationError('mode exige MANUAL ou SMA')
        decimal_value(self.initial_cash, 'initial_cash', positive=True)
        for name in ('fee_rate', 'slippage_rate'):
            if decimal_value(getattr(self, name), name) >= 1:
                raise ValidationError(f'{name} exige [0, 1)')
        if not isinstance(self.risk, RiskParameters) or not isinstance(self.instrument_filters, InstrumentFilters):
            raise ValidationError('Risco e filtros exigem modelos validados')
        if type(self.orders) is not tuple or not all(isinstance(r, RiskRequest) for r in self.orders):
            raise ValidationError('orders exige tuple de RiskRequest')
        if self.mode == 'SMA':
            if self.orders or not isinstance(self.strategy, SMAParameters):
                raise ValidationError('SMA exige strategy sem roteiro manual')
        elif self.strategy is not None:
            raise ValidationError('MANUAL não aceita strategy')
        seen, previous = {}, None
        for request in self.orders:
            if request.id in seen:
                if request != seen[request.id]:
                    raise ValidationError('ID de ação conflitante')
                continue
            if previous is not None and request.at_close < previous:
                raise ValidationError('Roteiro fora de ordem')
            seen[request.id], previous = request, request.at_close


@dataclass(frozen=True)
class RiskOrder:
    request: RiskRequest
    status: str
    submitted_seq: int
    reason: str | None = None
    quantity: Decimal = Decimal('0')
    sizing: dict | None = None
