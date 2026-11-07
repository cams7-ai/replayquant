"""Referências passivas isoladas; nenhum saldo é compartilhado com a estratégia."""
from decimal import Decimal
from fractions import Fraction
from .execution import effective_price
from .ledger import Ledger
from .models import Fill
from .validation import financial

QUANTUM = Decimal('0.000000000001')


@financial
def prepare_benchmarks(config, run_id, events):
    opening = next(e for e in events if e['type'] == 'OPEN')
    cash = Ledger.initial(config.initial_cash, run_id, 'HOLD_USDT', opening['at'])
    hold = Ledger.initial(config.initial_cash, run_id, 'BUY_HOLD_BTC', opening['at'])
    price = effective_price(opening['price'], 'BUY', config.slippage_rate)
    ideal = Fraction(config.initial_cash) / (Fraction(price) * (1 + Fraction(config.fee_rate)))
    steps = ideal / Fraction(QUANTUM)
    count = steps.numerator // steps.denominator
    quantity = Decimal((0, tuple(map(int, str(count))), -12))
    details = dict(quantity_quantum=QUANTUM, ideal_quantity=dict(numerator=str(ideal.numerator), denominator=str(ideal.denominator)),
                   quantity=quantity, entry_reference=opening['price'], entry_price=price)
    if not count:
        return [(cash, None, {}), (hold, 'BENCHMARK_SIZE_BELOW_QUANTUM', details)]
    gross = price * quantity
    fill = Fill('BUY_HOLD_BTC:entry:fill', 'BUY_HOLD_BTC:entry', 'BUY', quantity, price,
                gross * config.fee_rate, opening['at'])
    hold = hold.prepare(fill, opening['price'], opening['seq'])
    details['cash_residual'] = hold.balance.cash
    return [(cash, None, {}), (hold, None, details)]
