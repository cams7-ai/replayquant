"""Métricas com razões exatas; arredondamento somente na apresentação."""
from decimal import Decimal
from fractions import Fraction
from .validation import ValidationError, decimal_value, utc


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValidationError(f'{name}: esperado inteiro >= {minimum}')
    return value


def metric(value, unit, reason=None):
    if value is not None:
        if unit in ('COUNT', 'SECONDS'):
            integer(value, unit)
        elif not isinstance(value, Decimal) or not value.is_finite():
            raise ValidationError('Métrica monetária exige Decimal finito')
    return dict(value=value, unit=unit, reason=reason, numerator=None, denominator=None)


def ratio(value, unit='%'):
    if not isinstance(value, Fraction):
        raise ValidationError('Razão exige Fraction exato')
    # Divisão inteira com HALF_EVEN, independente do contexto Decimal externo.
    scaled, remainder = divmod(abs(value.numerator) * 10**12, value.denominator)
    twice = remainder * 2
    if twice > value.denominator or (twice == value.denominator and scaled % 2):
        scaled += 1
    digits = str(scaled).zfill(13)
    result = ('-' if value < 0 and scaled else '') + digits[:-12] + '.' + digits[-12:]
    return dict(value=result, unit=unit, reason=None,
                numerator=str(value.numerator), denominator=str(value.denominator))


def percentage(part, whole, reason='ZERO_OBSERVATION_DURATION'):
    if type(part) is bool or type(whole) is bool:
        raise ValidationError('Percentual não aceita booleano')
    return ratio(Fraction(part) / Fraction(whole) * 100) if whole else metric(None, '%', reason)


def seconds(start, end):
    start, end = utc(start), utc(end)
    elapsed = end - start
    if elapsed.microseconds or elapsed.days < 0:
        raise ValidationError('Duração exige segundos inteiros não negativos')
    return elapsed.days * 86400 + elapsed.seconds


def trade_statistics(profits):
    if type(profits) not in (list, tuple):
        raise ValidationError('Lucros exigem lista/tupla de Decimal')
    for value in profits:
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValidationError('Lucro exige Decimal finito')
    n = len(profits)
    return {
        'closed_trade_count': metric(n, 'COUNT'),
        'win_count': metric(sum(p > 0 for p in profits), 'COUNT'),
        'loss_count': metric(sum(p < 0 for p in profits), 'COUNT'),
        'break_even_count': metric(sum(p == 0 for p in profits), 'COUNT'),
        'win_rate_pct': percentage(sum(p > 0 for p in profits), n, 'NO_CLOSED_TRADES'),
        'expectancy': ratio(sum(map(Fraction, profits), Fraction()) / n, 'USDT/TRADE')
        if n else metric(None, 'USDT/TRADE', 'NO_CLOSED_TRADES'),
    }


def drawdowns(points):
    if type(points) not in (tuple, list) or not points:
        raise ValidationError('Curva deve conter pontos')
    previous_at, previous_seq = None, 0
    for point in points:
        if not isinstance(point, dict) or not {'point_seq', 'at', 'gross_equity'} <= point.keys():
            raise ValidationError('Ponto patrimonial incompleto')
        integer(point['point_seq'], 'point_seq', 1)
        at = utc(point['at'])
        decimal_value(point['gross_equity'], 'patrimônio', positive=True, bounded=False)
        if point['point_seq'] <= previous_seq or (previous_at is not None and at < previous_at):
            raise ValidationError('Curva fora de ordem')
        previous_at, previous_seq = at, point['point_seq']
    peak = points[0]
    episode = None
    episodes = []
    max_pct, max_amount = Fraction(), Fraction()
    max_episode = None
    for point in points:
        equity, high = Fraction(point['gross_equity']), Fraction(peak['gross_equity'])
        if equity >= high:
            if episode is not None:
                episode.update(recovered=True, recovery_at=point['at'], recovery_point_seq=point['point_seq'],
                               reason=None, observed_until=point['at'], duration_seconds=seconds(peak['at'], point['at']))
                episodes.append(episode)
                episode = None
            peak = point
            continue
        amount = high - equity
        pct = amount / high * 100
        if episode is None:
            episode = dict(peak_at=peak['at'], peak_point_seq=peak['point_seq'], peak_equity=peak['gross_equity'],
                           trough_at=point['at'], trough_point_seq=point['point_seq'], trough_equity=point['gross_equity'],
                           recovered=False, recovery_at=None, recovery_point_seq=None, reason='NOT_RECOVERED',
                           observed_until=points[-1]['at'], duration_seconds=0,
                           drawdown_amount=_finite_decimal(amount), drawdown_pct=ratio(pct))
        elif equity < Fraction(episode['trough_equity']):
            episode.update(trough_at=point['at'], trough_point_seq=point['point_seq'], trough_equity=point['gross_equity'],
                           drawdown_amount=_finite_decimal(amount), drawdown_pct=ratio(pct))
        if pct > max_pct:
            max_pct, max_episode = pct, episode
        max_amount = max(max_amount, amount)
    if episode is not None:
        episode['duration_seconds'] = seconds(episode['peak_at'], points[-1]['at'])
        episodes.append(episode)
    longest = max(episodes, key=lambda e: e['duration_seconds'], default=None)
    return dict(max_drawdown_pct=ratio(max_pct),
                max_drawdown_amount=metric(_finite_decimal(max_amount), 'USDT'),
                max_drawdown_duration_seconds=metric(longest['duration_seconds'] if longest else 0, 'SECONDS'),
                drawdown_episodes=episodes, max_drawdown_episode=max_episode,
                longest_drawdown_episode=longest, episode_reason=None if episodes else 'NO_DRAWDOWN')


def _finite_decimal(value):
    # Apenas razões originadas de diferenças de decimais finitos.
    n, d = value.numerator, value.denominator
    a = b = 0
    while d % 2 == 0:
        a += 1
        d //= 2
    while d % 5 == 0:
        b += 1
        d //= 5
    if d != 1:
        raise ValidationError('Razão monetária não decimal finita')
    scale = max(a, b)
    coefficient = abs(n) * 2**(scale-a) * 5**(scale-b)
    return Decimal((int(n < 0), tuple(map(int, str(coefficient))), -scale))
