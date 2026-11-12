"""Recorte explícito de janela/disponibilidade e cobertura do prefixo aceito."""
from .validation import ValidationError


def matching(candles, config):
    expected = config.source, config.symbol, config.interval
    if any((c.source, c.symbol, c.interval) != expected for c in candles):
        raise ValidationError('Dados de instrumento divergente da configuração')


def eligible(candle, config):
    return config.window.contains(candle.open_time, candle.close_time) and config.instrument.contains(candle.open_time, candle.close_time)


def describe(config, candles, accepted):
    start, end = config.window.start, config.window.end
    instrument = config.instrument
    effective_start = max(start, instrument.available_from)
    effective_end = min(end, instrument.available_until or end)
    expected = int((end-start).total_seconds()) // 60
    effective_expected = max(0, int((effective_end-effective_start).total_seconds()) // 60)
    eligible_candles = [c for c in candles if eligible(c, config)]
    excluded = dict(before_window=0, after_window=0, before_availability=0, after_availability=0)
    for c in candles:
        if c.open_time < start:
            excluded['before_window'] += 1
        elif c.close_time > end:
            excluded['after_window'] += 1
        elif c.open_time < instrument.available_from:
            excluded['before_availability'] += 1
        elif instrument.available_until is not None and c.close_time > instrument.available_until:
            excluded['after_availability'] += 1
    full = len(accepted) == expected and bool(accepted) and accepted[0].open_time == start and accepted[-1].close_time == end
    reasons = []
    if instrument.available_from > start:
        reasons.append('LATE_LISTING')
    if instrument.available_until is not None and instrument.available_until < end:
        reasons.append('EARLY_DELISTING')
    if effective_expected and not eligible_candles:
        reasons.append('MISSING_ELIGIBLE_DATA')
    if eligible_candles and eligible_candles[0].open_time > effective_start:
        reasons.append('DATA_START_MISSING')
    if eligible_candles and eligible_candles[-1].close_time < effective_end:
        reasons.append('DATA_END_MISSING')
    return dict(reasons=reasons, status='FULL' if full else ('PARTIAL' if accepted else 'NONE'),
                requested_start=start, requested_end=end, available_from=instrument.available_from,
                available_until=instrument.available_until, eligible_start=effective_start,
                eligible_end=effective_end, expected_candles=expected,
                expected_eligible_candles=effective_expected, eligible_candles=len(eligible_candles),
                accepted_candles=len(accepted), excluded=excluded,
                first_eligible=eligible_candles[0].open_time if eligible_candles else None,
                last_eligible=eligible_candles[-1].close_time if eligible_candles else None,
                observed_start=accepted[0].open_time if accepted else None,
                observed_until=accepted[-1].close_time if accepted else None,
                requested_coverage=dict(numerator=len(accepted), denominator=expected),
                eligible_coverage=dict(numerator=len(accepted), denominator=effective_expected) if effective_expected else None,
                missing_requested_candles=expected-len(accepted),
                missing_eligible_candles=effective_expected-len(accepted))
