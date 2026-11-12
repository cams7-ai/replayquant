"""Dimensionamento puro e bloqueios causais; razões exatas, sem float financeiro."""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from .execution import effective_price
from .metrics import integer, metric, ratio
from .risk_models import RiskConfig, RiskParameters
from .validation import ValidationError, decimal_value, financial, utc, identifier

ZERO = Decimal('0')
POLICY = 'SPRINT09_V1'


@dataclass(frozen=True)
class RiskSnapshot:
    equity: Decimal
    free_balance: Decimal
    exposure: Decimal
    price: Decimal | None
    price_at: object
    evaluated_at: object
    pending: bool = False
    position_open: bool = False
    reentry: bool = False
    daily_blocked: bool = False
    drawdown_blocked: bool = False

    @financial
    def __post_init__(self):
        for name in ('equity', 'free_balance', 'exposure'):
            decimal_value(getattr(self, name), name, bounded=False)
        if self.free_balance + self.exposure > self.equity:
            raise ValidationError('Snapshot inconsistente: disponível + exposição > patrimônio')
        object.__setattr__(self, 'evaluated_at', utc(self.evaluated_at))
        if self.price is not None:
            decimal_value(self.price, 'price', positive=True, bounded=False)
        if self.price_at is not None:
            object.__setattr__(self, 'price_at', utc(self.price_at))
            if self.price_at > self.evaluated_at:
                raise ValidationError('Preço futuro')
        for name in ('pending', 'position_open', 'reentry', 'daily_blocked', 'drawdown_blocked'):
            if type(getattr(self, name)) is not bool:
                raise ValidationError(f'{name} exige booleano')


def age_seconds(snapshot):
    delta = snapshot.evaluated_at - snapshot.price_at
    return Fraction(delta.days*86400 + delta.seconds) + Fraction(delta.microseconds, 1000000)


def price_reason(config, snapshot):
    if snapshot.price is None or snapshot.price_at is None:
        return 'PRICE_MISSING'
    if age_seconds(snapshot) > Fraction(config.risk.max_price_age_seconds):
        return 'PRICE_STALE'
    return None


@financial
def size_at(config, snapshot, entry=None, stop=None):
    """Componente aritmético reutilizável com stop absoluto explícito nos testes."""
    if not isinstance(config, RiskConfig) or not isinstance(snapshot, RiskSnapshot):
        raise ValidationError('Dimensionamento exige RiskConfig e RiskSnapshot')
    entry = effective_price(snapshot.price, 'BUY', config.slippage_rate) if entry is None else entry
    stop = entry*(1-config.risk.stop_fraction) if stop is None else stop
    decimal_value(entry, 'entry', positive=True, bounded=False)
    decimal_value(stop, 'stop', positive=True, bounded=False)
    if stop >= entry:
        raise ValidationError('Stop deve ser menor que entrada')
    target = entry*(1+config.risk.target_fraction)
    budget = snapshot.equity*config.risk.risk_fraction
    loss = entry*(1+config.fee_rate)-stop*(1-config.fee_rate)
    cap = snapshot.equity*config.risk.exposure_fraction
    candidates = {'risk': Fraction(budget)/Fraction(loss),
                  'exposure': max(Fraction(), Fraction(cap)-Fraction(snapshot.exposure))/Fraction(entry),
                  'cash': Fraction(snapshot.free_balance)/(Fraction(entry)*(1+Fraction(config.fee_rate)))}
    raw = min(candidates.values())
    count = raw // Fraction(config.instrument_filters.step)
    q = Decimal(count)*config.instrument_filters.step
    # Conversão/cálculos financeiros continuam sujeitos a representação exata.
    while True:
        outlay = q*entry*(1+config.fee_rate)
        planned_loss = outlay - q*stop*(1-config.fee_rate)
        if (outlay <= snapshot.free_balance and planned_loss <= budget
                and snapshot.exposure+q*entry <= cap and Fraction(q) <= raw):
            break
        count -= 1
        q = Decimal(count)*config.instrument_filters.step
    return dict(entry=entry, stop=stop, target=target, budget=budget, loss_per_unit=loss,
                max_exposure=cap, candidates={k: ratio(v, getattr(config, 'base_asset', 'BTC')) for k, v in candidates.items()},
                raw_quantity=ratio(raw, getattr(config, 'base_asset', 'BTC')), increments=count, candidate_quantity=q,
                limiters=[k for k, v in candidates.items() if v == raw],
                outlay=outlay, planned_loss=planned_loss, notional=q*entry,
                slippage_exit_loss=outlay-q*stop*(1-config.slippage_rate)*(1-config.fee_rate))


@financial
def evaluate(config, snapshot):
    if not isinstance(config, RiskConfig) or not isinstance(snapshot, RiskSnapshot):
        raise ValidationError('Avaliação exige modelos de risco')
    reason = next((reason for reason, blocked in (
        ('DAILY_LOSS_BLOCKED', snapshot.daily_blocked),
        ('DRAWDOWN_BLOCKED', snapshot.drawdown_blocked)) if blocked), None)
    reason = reason or price_reason(config, snapshot)
    if reason is None:
        reason = next((reason for reason, blocked in (
            ('ORDER_PENDING', snapshot.pending), ('POSITION_OPEN', snapshot.position_open),
            ('REENTRY_SAME_CANDLE', snapshot.reentry), ('NON_POSITIVE_EQUITY', snapshot.equity <= 0),
            ('EXPOSURE_LIMIT', snapshot.exposure >= snapshot.equity*config.risk.exposure_fraction),
            ('INSUFFICIENT_CASH', snapshot.free_balance == 0)) if blocked), None)
    sizing = None
    if reason is None:
        sizing = size_at(config, snapshot)
        filters = config.instrument_filters
        if (sizing['candidate_quantity'] == 0 or sizing['candidate_quantity'] < filters.min_quantity
                or sizing['notional'] < filters.min_notional):
            reason = 'BELOW_MINIMUMS'
    return dict(approved=reason is None, reason=reason, snapshot=snapshot, sizing=sizing,
                approved_quantity=sizing['candidate_quantity'] if reason is None else ZERO,
                sizing_reason=None if sizing is not None else 'NOT_EVALUATED')


@financial
def revalidate(config, snapshot, sizing):
    if not isinstance(config, RiskConfig) or not isinstance(snapshot, RiskSnapshot) or type(sizing) is not dict:
        raise ValidationError('Revalidação exige modelos e dimensionamento aprovado')
    for name in ('candidate_quantity','stop','target','budget'):
        decimal_value(sizing.get(name), name, positive=True, bounded=False)
    reason = ('DAILY_LOSS_BLOCKED' if snapshot.daily_blocked else
              ('DRAWDOWN_BLOCKED' if snapshot.drawdown_blocked else price_reason(config, snapshot)))
    if reason:
        return reason, None
    entry = effective_price(snapshot.price, 'BUY', config.slippage_rate)
    q, stop, target = sizing['candidate_quantity'], sizing['stop'], sizing['target']
    loss = q*(entry*(1+config.fee_rate)-stop*(1-config.fee_rate))
    outlay = q*entry*(1+config.fee_rate)
    details = dict(entry=entry, quantity=q, stop=stop, target=target,
                   budget=sizing['budget'], planned_loss=loss, outlay=outlay,
                   snapshot=snapshot)
    f = config.instrument_filters
    reason = next((reason for reason, failed in (
        ('POSITION_OPEN', snapshot.position_open),
        ('ENTRY_OUTSIDE_BRACKET', not stop < entry < target),
        ('RISK_BUDGET_EXCEEDED', loss > sizing['budget']),
        ('INSUFFICIENT_CASH', outlay > snapshot.free_balance),
        ('EXPOSURE_LIMIT', snapshot.exposure+q*entry > snapshot.equity*config.risk.exposure_fraction),
        ('BELOW_MINIMUMS', q < f.min_quantity or q*entry < f.min_notional)) if failed), None)
    return reason, details


@dataclass(frozen=True)
class EquityGuard:
    parameters: RiskParameters
    history: tuple[dict, ...] = ()

    def __post_init__(self):
        if not isinstance(self.parameters, RiskParameters):
            raise ValidationError('Bloqueios exigem RiskParameters')

    @property
    def current(self):
        return deepcopy(self.history[-1]) if self.history else None

    @financial
    def observe(self, at, source_event_seq, phase, equity):
        at = utc(at)
        integer(source_event_seq, 'source_event_seq')
        identifier(phase, 'phase')
        decimal_value(equity, 'equity', bounded=False)
        key = (at, source_event_seq, phase)
        for row in self.history:
            if (row['at'], row['source_event_seq'], row['phase']) == key:
                if row['equity'] != equity:
                    raise ValidationError('Observação patrimonial conflitante')
                return self
        previous = self.current
        if previous and (at < previous['at'] or source_event_seq <= previous['source_event_seq']):
            raise ValidationError('Observação fora de ordem')
        if previous is None and equity == 0:
            raise ValidationError('Primeiro patrimônio deve ser positivo')
        new_day = previous is None or at.date() != previous['at'].date()
        base = None if new_day else previous['daily_base']
        base_at = None if new_day else previous['daily_base_at']
        if base is None and equity > 0:
            base, base_at = equity, at
        peak = equity if previous is None else max(previous['peak'], equity)
        daily = max(Fraction(), (Fraction(base)-Fraction(equity))/Fraction(base)) if base else None
        dd = (Fraction(peak)-Fraction(equity))/Fraction(peak)
        row = dict(at=at, source_event_seq=source_event_seq, phase=phase, equity=equity, peak=peak,
                   daily_base=base, daily_base_at=base_at,
                   daily_base_partial=base_at is not None and (base_at.hour, base_at.minute, base_at.second, base_at.microsecond) != (0,0,0,0),
                   daily_loss=ratio(daily, 'FRACTION') if daily is not None else metric(None, 'FRACTION', 'NO_POSITIVE_DAILY_BASE'),
                   drawdown=ratio(dd, 'FRACTION'),
                   daily_blocked=(equity == 0 or (daily is not None and daily >= Fraction(self.parameters.daily_loss_fraction))
                                  or (not new_day and previous['daily_blocked'])),
                   drawdown_blocked=(equity == 0 or dd >= Fraction(self.parameters.drawdown_fraction)
                                     or (previous is not None and previous['drawdown_blocked'])))
        return EquityGuard(self.parameters, (*self.history, row))
