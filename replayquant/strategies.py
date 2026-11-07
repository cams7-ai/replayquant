"""SMA incremental: somente fechamentos liberados, razões exatas para decisões."""
from collections import deque
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
