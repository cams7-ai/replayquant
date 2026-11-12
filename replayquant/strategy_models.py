"""Identidade imutável e parâmetros das estratégias schema 5."""
from dataclasses import dataclass
from decimal import Decimal
from .metrics import integer
from .validation import ValidationError, decimal_value


@dataclass(frozen=True)
class CrossParameters:
    short_window: int
    long_window: int

    def __post_init__(self):
        integer(self.short_window, 'short_window', 1)
        integer(self.long_window, 'long_window', 2)
        if self.short_window >= self.long_window:
            raise ValidationError('Janelas exigem curta < longa')


@dataclass(frozen=True)
class RSIParameters:
    period: int
    oversold: Decimal
    overbought: Decimal

    def __post_init__(self):
        integer(self.period, 'period', 1)
        decimal_value(self.oversold, 'oversold', positive=True)
        decimal_value(self.overbought, 'overbought', positive=True)
        if not self.oversold < self.overbought < 100:
            raise ValidationError('RSI exige 0 < oversold < overbought < 100')


@dataclass(frozen=True)
class StrategySpec:
    name: str
    version: int
    parameters: CrossParameters | RSIParameters

    def __post_init__(self):
        if type(self.name) is not str or self.name not in ('SMA_CROSS', 'EMA_CROSS', 'RSI_REVERSION'):
            raise ValidationError('Estratégia desconhecida')
        if type(self.version) is not int or self.version != 1:
            raise ValidationError('Versão de estratégia desconhecida')
        expected = RSIParameters if self.name == 'RSI_REVERSION' else CrossParameters
        if type(self.parameters) is not expected:
            raise ValidationError('Parâmetros incompatíveis com a estratégia')

    @property
    def warmup_candles(self):
        if isinstance(self.parameters, RSIParameters):
            return self.parameters.period + 2
        return self.parameters.long_window + 1

    @property
    def policy(self):
        seed = {'SMA_CROSS': 'ROLLING_WINDOW', 'EMA_CROSS': 'SMA_SEED',
                'RSI_REVERSION': 'WILDER_SMA_SEED_FLAT_50'}[self.name]
        return dict(seed=seed, arithmetic='EXACT_RATIONAL', decimal_places=12,
                    rounding='ROUND_HALF_EVEN')
