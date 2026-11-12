"""Registros imutáveis; validação também em construções diretas pela API."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from .validation import ValidationError, decimal_value, identifier, utc


def instrument(source, symbol, interval):
    if (source, symbol, interval) != ("FICTICIA", "BTCUSDT", "1m"):
        raise ValidationError("Instrumento permitido: FICTICIA/BTCUSDT/1m")



def market_instrument(source, symbol, interval):
    import re
    if (type(source) is not str or source != 'FICTICIA' or type(symbol) is not str
            or re.fullmatch(r'[A-Z0-9]{2,30}', symbol) is None or type(interval) is not str or interval != '1m'):
        raise ValidationError('Identidade de mercado inválida')

def side_value(side):
    if type(side) is not str or side not in ("BUY", "SELL"):
        raise ValidationError("side deve ser BUY ou SELL")


@dataclass(frozen=True)
class Candle:
    source: str
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool

    def __post_init__(self):
        market_instrument(self.source, self.symbol, self.interval)
        for name in ("open_time", "close_time"):
            object.__setattr__(self, name, utc(getattr(self, name), name))
        if self.open_time.second or self.open_time.microsecond:
            raise ValidationError("Abertura deve estar alinhada ao minuto")
        if self.close_time - self.open_time != timedelta(minutes=1):
            raise ValidationError("Candle deve durar exatamente um minuto")
        for name in ("open", "high", "low", "close"):
            decimal_value(getattr(self, name), name, positive=True)
        decimal_value(self.volume, "volume")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValidationError("OHLC inconsistente")
        if type(self.is_closed) is not bool or not self.is_closed:
            raise ValidationError("Replay exige candle fechado")

    @property
    def key(self):
        return self.source, self.symbol, self.interval, self.open_time

    def opening(self):
        return Opening(self.source, self.symbol, self.interval, self.open_time, self.open)


@dataclass(frozen=True)
class Opening:
    """Informação liberada na abertura, sem acesso ao restante do OHLCV."""
    source: str
    symbol: str
    interval: str
    at: datetime
    price: Decimal

    def __post_init__(self):
        market_instrument(self.source, self.symbol, self.interval)
        object.__setattr__(self, "at", utc(self.at))
        if self.at.second or self.at.microsecond:
            raise ValidationError("Abertura deve estar alinhada ao minuto")
        decimal_value(self.price, "price", positive=True)


@dataclass(frozen=True)
class Request:
    id: str
    at_close: datetime
    side: str

    def __post_init__(self):
        identifier(self.id)
        object.__setattr__(self, "at_close", utc(self.at_close))
        side_value(self.side)


@dataclass(frozen=True)
class Config:
    source: str
    symbol: str
    interval: str
    initial_cash: Decimal
    quantity: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    orders: tuple[Request, ...]

    def __post_init__(self):
        instrument(self.source, self.symbol, self.interval)
        decimal_value(self.initial_cash, "initial_cash", positive=True)
        decimal_value(self.quantity, "quantity", positive=True)
        decimal_value(self.fee_rate, "fee_rate")
        decimal_value(self.slippage_rate, "slippage_rate")
        if self.fee_rate >= 1 or self.slippage_rate != 0:
            raise ValidationError("Taxa exige [0, 1) e slippage deve ser zero")
        if type(self.orders) is not tuple or not all(isinstance(r, Request) for r in self.orders):
            raise ValidationError("orders deve ser tuple de Request")
        seen = {}
        previous = None
        for request in self.orders:
            if request.id in seen:
                if seen[request.id] != request:
                    raise ValidationError("ID de ordem conflitante")
                continue
            if previous is not None and request.at_close < previous:
                raise ValidationError("Roteiro fora de ordem temporal")
            seen[request.id] = request
            previous = request.at_close


@dataclass(frozen=True)
class SMAParameters:
    name: str
    short_window: int
    long_window: int

    def __post_init__(self):
        if (self.name != "SMA_CROSS" or type(self.name) is not str
                or type(self.short_window) is not int or type(self.long_window) is not int
                or not 1 <= self.short_window < self.long_window):
            raise ValidationError("SMA_CROSS exige janelas inteiras 1 <= curta < longa")


@dataclass(frozen=True)
class SMAConfig:
    source: str
    symbol: str
    interval: str
    initial_cash: Decimal
    quantity: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    strategy: SMAParameters

    def __post_init__(self):
        instrument(self.source, self.symbol, self.interval)
        decimal_value(self.initial_cash, "initial_cash", positive=True)
        decimal_value(self.quantity, "quantity", positive=True)
        for name in ("fee_rate", "slippage_rate"):
            if decimal_value(getattr(self, name), name) >= 1:
                raise ValidationError(f"{name} exige [0, 1)")
        if not isinstance(self.strategy, SMAParameters):
            raise ValidationError("strategy exige SMAParameters")


@dataclass(frozen=True)
class Order:
    request: Request
    status: str
    submitted_seq: int
    reason: str | None = None


@dataclass(frozen=True)
class Fill:
    id: str
    order_id: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    at: datetime

    def __post_init__(self):
        identifier(self.id)
        identifier(self.order_id, "order_id")
        side_value(self.side)
        decimal_value(self.quantity, "quantity", positive=True, bounded=False)
        decimal_value(self.price, "price", positive=True, bounded=False)
        decimal_value(self.fee, "fee", bounded=False)
        object.__setattr__(self, "at", utc(self.at))
