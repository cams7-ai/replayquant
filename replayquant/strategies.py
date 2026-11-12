"""SMA incremental: somente fechamentos liberados, razões exatas para decisões."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from typing import Protocol
from .metrics import ratio as presented_ratio
from .strategy_models import StrategySpec, CrossParameters, RSIParameters
from fractions import Fraction
from .models import Candle, SMAParameters
from .validation import ValidationError


def ratio(value):
    if value is None:
        return None
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


class SMACross:
    def __init__(self, parameters):
        if not isinstance(parameters, SMAParameters):
            raise ValidationError("Esperado SMAParameters")
        self.parameters = parameters
        self._history = deque(maxlen=parameters.long_window)
        self._previous = None
        self.count = 0

    def on_close(self, candle):
        if not isinstance(candle, Candle):
            raise ValidationError("Indicador exige Candle fechado")
        self._history.append(Fraction(candle.close))
        self.count += 1
        s, l = self.parameters.short_window, self.parameters.long_window
        history = list(self._history)
        short = sum(history[-s:], Fraction()) / s if len(history) >= s else None
        long = sum(history, Fraction()) / l if len(history) >= l else None
        current = None if long is None else (short > long) - (short < long)
        previous = self._previous
        side = None
        if previous is not None and current is not None:
            if previous <= 0 < current:
                side = "BUY"
            elif previous >= 0 > current:
                side = "SELL"
        self._previous = current
        return {"count": self.count, "short": ratio(short), "long": ratio(long),
                "missing_reason": "WARMUP" if short is None or long is None else None,
                "previous_comparison": previous, "comparison": current,
                "side": side, "reason": "WARMUP" if previous is None else
                (None if side else "NO_CROSS")}


class EMACross:
    """Cada EMA começa com a SMA da sua própria janela."""
    def __init__(self, parameters):
        if not isinstance(parameters, CrossParameters):
            raise ValidationError('EMA exige CrossParameters')
        self.parameters = parameters
        self.history = deque(maxlen=parameters.long_window)
        self.short = self.long = None
        self.previous = None
        self.count = 0

    def _next(self, value, window, close):
        if self.count < window:
            return None
        if value is None:
            return sum(list(self.history)[-window:], Fraction()) / window
        alpha = Fraction(2, window + 1)
        return alpha * close + (1 - alpha) * value

    def on_close(self, candle):
        if not isinstance(candle, Candle):
            raise ValidationError('Indicador exige Candle fechado')
        close = Fraction(candle.close)
        self.history.append(close)
        self.count += 1
        self.short = self._next(self.short, self.parameters.short_window, close)
        self.long = self._next(self.long, self.parameters.long_window, close)
        comparison = None if self.long is None else (self.short > self.long) - (self.short < self.long)
        previous = self.previous
        side = None
        if previous is not None and comparison is not None:
            if previous <= 0 < comparison:
                side = 'BUY'
            elif previous >= 0 > comparison:
                side = 'SELL'
        self.previous = comparison
        return dict(count=self.count, short=ratio(self.short), long=ratio(self.long),
                    previous_comparison=previous, comparison=comparison, side=side,
                    reason='WARMUP' if previous is None else (None if side else 'NO_CROSS'))


class RSIReversion:
    def __init__(self, parameters):
        if not isinstance(parameters, RSIParameters):
            raise ValidationError('RSI exige RSIParameters')
        self.parameters = parameters
        self.count = 0
        self.previous_close = None
        self.gain = self.loss = Fraction()
        self.previous = None

    def on_close(self, candle):
        if not isinstance(candle, Candle):
            raise ValidationError('Indicador exige Candle fechado')
        self.count += 1
        close = Fraction(candle.close)
        n = self.parameters.period
        if self.previous_close is not None:
            delta = close - self.previous_close
            gain, loss = max(delta, 0), max(-delta, 0)
            if self.count <= n + 1:
                self.gain += Fraction(gain, n)
                self.loss += Fraction(loss, n)
            else:
                self.gain = ((n - 1) * self.gain + gain) / n
                self.loss = ((n - 1) * self.loss + loss) / n
        self.previous_close = close
        current = None
        diagnostic = None
        if self.count >= n + 1:
            total = self.gain + self.loss
            current = 100 * self.gain / total if total else Fraction(50)
            if not total:
                diagnostic = 'FLAT_SEED_OR_STATE'
        side = None
        if self.previous is not None:
            if self.previous <= Fraction(self.parameters.oversold) < current:
                side = 'BUY'
            elif self.previous >= Fraction(self.parameters.overbought) > current:
                side = 'SELL'
        def comparisons(value):
            if value is None:
                return None
            return {name: (value > Fraction(threshold)) - (value < Fraction(threshold))
                    for name, threshold in [('oversold', self.parameters.oversold),
                                            ('overbought', self.parameters.overbought)]}

        result = dict(count=self.count, rsi=ratio(current), previous_rsi=ratio(self.previous),
                      comparison=comparisons(current), previous_comparison=comparisons(self.previous),
                      avg_gain=ratio(self.gain) if current is not None else None,
                      avg_loss=ratio(self.loss) if current is not None else None,
                      side=side, diagnostic=diagnostic,
                      reason='WARMUP' if self.previous is None else (None if side else 'NO_CROSS'))
        self.previous = current
        return result


class Strategy(Protocol):
    spec: StrategySpec

    def on_close(self, candle: Candle) -> dict: ...


class ModularStrategy:
    """Fronteira validada e avaliação comum, com decisões racionais exatas."""
    def __init__(self, spec, indicator, base_asset='BTC'):
        self.base_asset = base_asset
        self.spec = spec
        self.indicator = indicator
        self._seen = {}
        self._last = None
        self._values = None

    def on_close(self, candle):
        if not isinstance(candle, Candle):
            raise ValidationError('Estratégia exige Candle fechado')
        if candle.key in self._seen:
            previous, evaluation = self._seen[candle.key]
            if previous != candle:
                raise ValidationError('Candle conflitante')
            return deepcopy(evaluation)
        if self._last is not None and candle.open_time != self._last.close_time:
            raise ValidationError('Estratégia exige fechamentos contíguos e ordenados')
        candidate = deepcopy(self.indicator)
        result = candidate.on_close(candle)
        unit = 'RSI_POINTS' if self.spec.name == 'RSI_REVERSION' else 'USDT/' + self.base_asset
        keys = ('rsi',) if self.spec.name == 'RSI_REVERSION' else ('short', 'long')
        values = {}
        for key in (*keys, 'previous_rsi', 'avg_gain', 'avg_loss'):
            if key in result and result[key] is not None:
                raw = result[key]
                result[key] = presented_ratio(Fraction(int(raw['numerator']), int(raw['denominator'])),
                                              'USDT/' + self.base_asset if key in ('avg_gain', 'avg_loss') else unit)
            if key in keys:
                values[key] = result.get(key)
        ready = all(v is not None for v in values.values())
        signal_ready = ready and self._values is not None and all(v is not None for v in self._values.values())
        reason = result['reason']
        if result['side']:
            if self.spec.name == 'RSI_REVERSION':
                reason = 'EXIT_OVERSOLD' if result['side'] == 'BUY' else 'EXIT_OVERBOUGHT'
            else:
                reason = 'CROSS_UP' if result['side'] == 'BUY' else 'CROSS_DOWN'
        result.update(strategy=asdict(self.spec), indicator_policy=self.spec.policy,
                      candle_key=candle.key, available_at=candle.close_time,
                      indicator_ready=ready, signal_ready=signal_ready,
                      previous_values=deepcopy(self._values), values=values,
                      missing_reason=None if signal_ready else 'WARMUP', reason=reason)
        self.indicator = candidate
        self._last, self._values = candle, deepcopy(values)
        self._seen[candle.key] = (candle, deepcopy(result))
        return deepcopy(result)


class StrategyRegistry:
    def __init__(self):
        self._factories = {}

    def register(self, name, version, factory):
        if type(name) is not str or type(version) is not int or version < 1 or not callable(factory):
            raise ValidationError('Registro de estratégia inválido')
        key = name, version
        if key in self._factories:
            raise ValidationError('Registro de estratégia duplicado')
        self._factories[key] = factory

    def create(self, spec: StrategySpec, base_asset='BTC') -> Strategy:
        if not isinstance(spec, StrategySpec):
            raise ValidationError('Esperado StrategySpec')
        factory = self._factories.get((spec.name, spec.version))
        if factory is None:
            raise ValidationError('Estratégia/versão não registrada')
        return ModularStrategy(spec, factory(spec.parameters), base_asset)


REGISTRY = StrategyRegistry()
REGISTRY.register('SMA_CROSS', 1, lambda p: SMACross(SMAParameters('SMA_CROSS', p.short_window, p.long_window)))
REGISTRY.register('EMA_CROSS', 1, EMACross)
REGISTRY.register('RSI_REVERSION', 1, RSIReversion)
