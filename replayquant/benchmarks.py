"""Referências passivas isoladas; nenhum saldo é compartilhado com a estratégia."""
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from .execution import effective_price
from .ledger import Ledger
from .models import Fill
from .validation import financial

QUANTUM = Decimal('0.000000000001')


@financial
def _prepare_benchmarks(config, run_id, events):
    opening = next(e for e in events if e['type'] == 'OPEN')
    cash = Ledger.initial(config.initial_cash, run_id, 'HOLD_USDT', opening['at'])
    hold = Ledger.initial(config.initial_cash, run_id, 'BUY_HOLD_BTC', opening['at'])
    price = effective_price(opening['price'], 'BUY', config.slippage_rate)
    ideal = Fraction(config.initial_cash) / (Fraction(price) * (1 + Fraction(config.fee_rate)))
    filters = getattr(config, 'instrument_filters', None)
    quantum = filters.step if filters else QUANTUM
    steps = ideal / Fraction(quantum)
    count = steps.numerator // steps.denominator
    quantity = Decimal(count)*quantum
    details = dict(quantity_quantum=quantum, ideal_quantity=dict(numerator=str(ideal.numerator), denominator=str(ideal.denominator)),
                   quantity=quantity, entry_reference=opening['price'], entry_price=price)
    if filters:
        details.update(instrument_filters=filters, risk_policy='PASSIVE_NO_STOPS_OR_BLOCKS')
    if not count:
        reason = 'BENCHMARK_BELOW_MINIMUMS' if filters else 'BENCHMARK_SIZE_BELOW_QUANTUM'
        return [(cash, None, {}), (hold, reason, details)]
    if filters:
        if quantity < filters.min_quantity or quantity*price < filters.min_notional:
            return [(cash, None, {}), (hold, 'BENCHMARK_BELOW_MINIMUMS', details)]
    gross = price * quantity
    fill = Fill('BUY_HOLD_BTC:entry:fill', 'BUY_HOLD_BTC:entry', 'BUY', quantity, price,
                gross * config.fee_rate, opening['at'])
    hold = hold.prepare(fill, opening['price'], opening['seq'])
    details['cash_residual'] = hold.balance.cash
    return [(cash, None, {}), (hold, None, details)]


def prepare_benchmarks(config, run_id, events):
    rows = _prepare_benchmarks(config, run_id, events)
    if getattr(config, 'mode', None) in ('MANUAL','SMA'):
        rows = [(replace(ledger, entries=tuple(replace(e, schema_version=4) for e in ledger.entries)), reason, details)
                for ledger, reason, details in rows]
    return rows
