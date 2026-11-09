"""Grupo único de stop/alvo; resolução OHLC explicitamente aproximada."""
from dataclasses import dataclass
from .validation import decimal_value, identifier, utc, ValidationError


@dataclass(frozen=True)
class Protection:
    id: str
    lot_id: str
    quantity: object
    stop: object
    target: object
    budget: object
    entry_at: object
    eligible_at: object
    status: str = 'ACTIVE'
    exit_details: dict | None = None

    def __post_init__(self):
        identifier(self.id)
        identifier(self.lot_id)
        for name in ('quantity', 'stop', 'target', 'budget'):
            decimal_value(getattr(self, name), name, positive=True, bounded=False)
        for name in ('entry_at', 'eligible_at'):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if self.stop >= self.target or self.eligible_at <= self.entry_at:
            raise ValidationError('Grupo protetivo inconsistente')
        if self.status not in ('ACTIVE', 'CLOSED', 'ENDED_WITH_OPEN_POSITION'):
            raise ValidationError('Estado protetivo inválido')


def opening_trigger(group, opening):
    if group is None or group.status != 'ACTIVE' or opening.at < group.eligible_at:
        return None
    side = 'STOP' if opening.price <= group.stop else ('TARGET' if opening.price >= group.target else None)
    if side is None:
        return None
    return dict(exit_origin=side, reference_price=opening.price, ambiguous=False,
                stop_touched=side == 'STOP', target_touched=side == 'TARGET',
                execution_time_model='OPEN_EVENT', intrabar_time_known=True,
                interval_start=opening.at, interval_end=opening.at)


def range_trigger(group, candle):
    if group is None or group.status != 'ACTIVE' or candle.open_time < group.eligible_at:
        return None
    stop, target = candle.low <= group.stop, candle.high >= group.target
    if not stop and not target:
        return None
    return dict(exit_origin='STOP' if stop else 'TARGET', reference_price=group.stop if stop else group.target,
                stop_touched=stop, target_touched=target, ambiguous=stop and target,
                ambiguity_policy='STOP_FIRST', execution_time_model='BAR_CLOSE_RESOLUTION',
                intrabar_time_known=False, interval_start=candle.open_time, interval_end=candle.close_time)
