"""Projeção causal de ledger/quotes aceitos; análise não decide operações."""
from copy import deepcopy
from decimal import Decimal
from .benchmarks import prepare_benchmarks
from .metrics import drawdowns, metric, percentage, trade_statistics, seconds
from .validation import ValidationError, financial

POLICY = 'SPRINT08_V1'
ZERO = Decimal('0')


def analysis_flag(value):
    if type(value) is not bool:
        raise ValidationError('analysis exige booleano')
    return value


@financial
def project_curve(ledger, events, config):
    """Lê deltas já comprometidos, sem repetir execuções ou consultar candles futuros."""
    ledger.reconcile()
    initial = ledger.entries[0]
    current = initial
    realized = ZERO
    mark = mark_at = None
    points = []
    by_seq = {entry.source_event_seq: entry for entry in ledger.entries[1:]}
    pnl_by_fill = {trade.sell_execution_id: trade.net_pnl for trade in ledger.trades}
    applied = set()

    def point(at, source_seq, phase):
        cash, q, basis = current.cash_after, current.asset_after, current.cost_basis_after
        if mark is None and q != 0:
            raise ValidationError('Posição sem preço disponível')
        position_value = q * mark if q else ZERO
        equity = cash + position_value
        unrealized = position_value - basis
        liquidation_gross = q * mark * (1 - config.slippage_rate) if q else ZERO
        liquidation_fee = liquidation_gross * config.fee_rate
        hypothetical = cash + liquidation_gross - liquidation_fee
        if equity != config.initial_cash + realized + unrealized:
            raise ValidationError('RECONCILIATION_FAILED: patrimônio')
        points.append(dict(schema_version=3, run_id=initial.run_id, portfolio=initial.portfolio,
                           point_seq=len(points)+1, at=at, source_event_seq=source_seq, phase=phase,
                           cash_total=cash, cash_available=cash, cash_reserved=ZERO, asset_quantity=q,
                           mark_price=mark, mark_at=mark_at, mark_reason='NO_MARKET_PRICE_YET' if mark is None else None,
                           cost_basis=basis, realized_pnl=realized, unrealized_pnl=unrealized,
                           gross_equity=equity, hypothetical_liquidation_equity=hypothetical,
                           hypothetical_exit_fee=liquidation_fee,
                           hypothetical_exit_slippage=position_value-liquidation_gross))
    point(initial.at, 0, 'INITIAL')
    for event in events:
        kind = event['type']
        if kind in ('OPEN', 'CLOSE'):
            mark = event['price'] if kind == 'OPEN' else event['candle'].close
            mark_at = event['at']
            point(event['at'], event['seq'], kind)
        if event['seq'] in by_seq:
            entry = by_seq[event['seq']]
            if kind not in ('OPEN', 'FILLED') or entry.at != event['at']:
                raise ValidationError('RECONCILIATION_FAILED: origem do fill')
            if initial.portfolio == 'STRATEGY' and (kind != 'FILLED' or event['execution_id'] != entry.execution_id):
                raise ValidationError('RECONCILIATION_FAILED: referência do fill')
            current = entry
            realized += pnl_by_fill.get(entry.execution_id, ZERO)
            applied.add(event['seq'])
            point(event['at'], event['seq'], 'FILL')
    if applied != set(by_seq) or current != ledger.entries[-1]:
        raise ValidationError('RECONCILIATION_FAILED: ledger fora do prefixo')
    return points


@financial
def portfolio_analysis(ledger, events, config):
    curve = project_curve(ledger, events, config)
    last = curve[-1]
    duration = seconds(curve[0]['at'], last['at'])
    exposure = sum(t.duration_seconds for t in ledger.trades)
    if ledger.open_fill:
        exposure += seconds(ledger.open_fill.at, last['at'])
    if exposure > duration:
        raise ValidationError('Tempo de posição excede horizonte')
    metrics = trade_statistics([t.net_pnl for t in ledger.trades])
    metrics.update(realized_pnl=metric(ledger.realized, 'USDT'),
                   unrealized_pnl=metric(last['unrealized_pnl'], 'USDT'),
                   final_cash=metric(last['cash_total'], 'USDT'),
                   final_asset_quantity=metric(last['asset_quantity'], 'BTC'),
                   final_gross_equity=metric(last['gross_equity'], 'USDT'),
                   final_hypothetical_liquidation_equity=metric(last['hypothetical_liquidation_equity'], 'USDT'),
                   portfolio_return_pct=percentage(last['gross_equity']-config.initial_cash, config.initial_cash),
                   hypothetical_liquidation_return_pct=percentage(last['hypothetical_liquidation_equity']-config.initial_cash, config.initial_cash),
                   paid_fees=metric(ledger.fees, 'USDT'), slippage_impact=metric(ledger.slippage, 'USDT'),
                   attributed_execution_costs=metric(ledger.fees+ledger.slippage, 'USDT'),
                   observation_duration_seconds=metric(duration, 'SECONDS'),
                   time_in_position_seconds=metric(exposure, 'SECONDS'),
                   time_in_position_pct=percentage(exposure, duration))
    dd = drawdowns(curve)
    for name in ('max_drawdown_pct', 'max_drawdown_amount', 'max_drawdown_duration_seconds'):
        metrics[name] = dd.pop(name)
    opened = None
    if ledger.open_fill:
        opened = dict(lot_id=f'{ledger.open_fill.id}:lot', execution_id=ledger.open_fill.id,
                      quantity=ledger.open_fill.quantity, entry_at=ledger.open_fill.at, cost_basis=ledger.cost_basis,
                      mark_price=last['mark_price'], mark_at=last['mark_at'],
                      unrealized_pnl=last['unrealized_pnl'], hypothetical_exit_fee=last['hypothetical_exit_fee'],
                      hypothetical_exit_slippage=last['hypothetical_exit_slippage'])
    reconciliation = ledger.reconcile()
    reconciliation.update(equity_points_checked=len(curve), equity_identity_difference=ZERO, gross_equity=last['gross_equity'])
    return dict(metrics=metrics, equity_curve=curve, closed_trades=[t.export() for t in ledger.trades],
                open_position=opened, ledger_entries=ledger.entries, reconciliation=reconciliation, **dd)


@financial
def analyze(session):
    events = session.events
    if not any(e['type'] == 'CLOSE' for e in events):
        raise ValidationError('Análise exige ao menos um fechamento aceito')
    interrupted = getattr(session, 'status', None) == 'INTERRUPTED'
    result = portfolio_analysis(session.ledger, events, session.config)
    if session.ledger.balance != session.balance or session.ledger.fees != session.fees:
        raise ValidationError('RECONCILIATION_FAILED: sessão')
    start = session.ledger.entries[0].at
    end = result['equity_curve'][-1]['at']
    references = []
    for ledger, reason, details in prepare_benchmarks(session.config, session.run_id, events):
        name = ledger.entries[0].portfolio
        item = dict(portfolio=name, status='UNAVAILABLE' if reason else ('INTERRUPTED' if interrupted else 'COMPLETED'),
                    reason=reason or ((session.diagnostic or {}).get('reason', 'INTERRUPTED') if interrupted else None),
                    observation_start=start, observed_until=end, initial_cash=session.config.initial_cash,
                    parameters=details)
        if reason:
            item.update(metrics={}, equity_curve=[], ledger_entries=ledger.entries,
                        reconciliation=ledger.reconcile(), closed_trades=[], open_position=None)
        else:
            item.update(portfolio_analysis(ledger, events, session.config))
        references.append(item)
    result.update(policy_version=POLICY, scope='ACCEPTED_PREFIX' if interrupted else 'FULL_RUN',
                  position_at_end='KEEP_OPEN', observation_start=start, observed_until=end, benchmarks=references,
                  rounding_policy=dict(ratio_decimal_places=12, rounding='ROUND_HALF_EVEN', decisions='EXACT_RATIOS'),
                  sampling_policy='INITIAL_OPEN_BEFORE_FILL_FILL_AFTER_CLOSE', no_cash_flows=True,
                  execution_cost_policy=dict(fee_rate=session.config.fee_rate, slippage_rate=session.config.slippage_rate,
                                             strategy_quantity=session.config.quantity, fee_currency='USDT'))
    return deepcopy(result)
