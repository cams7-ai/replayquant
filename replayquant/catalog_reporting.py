"""Metadados e relatórios de instrumento, inclusive interseção sem observações."""
from dataclasses import asdict
from decimal import Decimal
from .coverage import describe
from .metrics import metric, trade_statistics
from .portfolio import AssetBalance


def instrument_report(summary, session):
    config = session.config
    accepted = [e['candle'] for e in session.events if e['type'] == 'CLOSE']
    source = session._source_candles or tuple(accepted)
    summary.update(base_asset=config.base_asset, quote_asset='USDT', symbol=config.symbol,
                   source=config.source, interval=config.interval, instrument=config.instrument,
                   catalog=config.catalog, window=config.window,
                   coverage=describe(config, source, accepted),
                   units=dict(cash='USDT', asset_quantity=config.base_asset,
                              price=f'USDT/{config.base_asset}', fee='USDT'))
    summary['coverage']['duplicates'] = sum(r.get('reason') == 'DUPLICATE_CANDLE' for r in session._input_diagnostics)
    summary['coverage']['gaps'] = [session.diagnostic] if (session.diagnostic or {}).get('reason') == 'DATA_GAP' else []


def unavailable_report(summary, session):
    from .risk_reporting import LIMITATIONS
    from .reporting import wire
    config = session.config
    zero = Decimal(0)
    reason = 'NO_ELIGIBLE_CANDLES'
    metrics = trade_statistics([])
    for key, unit in [('realized_pnl', 'USDT'), ('unrealized_pnl', 'USDT'),
                      ('final_gross_equity', 'USDT'), ('final_hypothetical_liquidation_equity', 'USDT'),
                      ('max_drawdown_amount', 'USDT'), ('max_drawdown_duration_seconds', 'SECONDS'),
                      ('observation_duration_seconds', 'SECONDS'), ('time_in_position_seconds', 'SECONDS')]:
        metrics[key] = metric(None, unit, reason)
    for key in ['portfolio_return_pct', 'hypothetical_liquidation_return_pct', 'max_drawdown_pct', 'time_in_position_pct']:
        metrics[key] = metric(None, '%', reason)
    metrics.update(final_cash=metric(config.initial_cash, 'USDT'), final_asset_quantity=metric(zero, config.base_asset),
                   paid_fees=metric(zero, 'USDT'), slippage_impact=metric(zero, 'USDT'),
                   attributed_execution_costs=metric(zero, 'USDT'))
    references = [dict(portfolio=name, status='UNAVAILABLE', reason=reason, metrics={},
                       observation_start=None, observed_until=None, initial_cash=config.initial_cash,
                       parameters={}, equity_curve=[], ledger_entries=[], closed_trades=[], open_position=None,
                       reconciliation=dict(status='NOT_APPLICABLE', reason=reason))
                  for name in ('HOLD_USDT', 'BUY_HOLD_ASSET')]
    analysis = dict(metrics=metrics, equity_curve=[], closed_trades=[], open_position=None, ledger_entries=[],
                    reconciliation=dict(status='NOT_APPLICABLE', reason=reason,
                                        reconstructed_cash=config.initial_cash, reconstructed_asset=zero),
                    benchmarks=references, drawdown_episodes=[], episode_reason=reason, scope='NO_OBSERVATIONS',
                    policy_version='SPRINT09_V1', position_at_end='KEEP_OPEN',
                    observation_start=None, observed_until=None,
                    execution_cost_policy=dict(fee_rate=config.fee_rate, slippage_rate=config.slippage_rate,
                                               strategy_quantity=None, fee_currency='USDT'))
    summary.update(schema_version=6, input_config_schema_version=6, simulation_mode='STRATEGY',
                   status='UNAVAILABLE', exit_code=2, diagnostic=dict(reason=reason), pending_order_id=None,
                   strategy=config.strategy, indicator_policy=config.strategy.policy,
                   evaluations=[], signals=[], decisions=[], intentions=[], candles=[],
                   final_balance=AssetBalance(config.initial_cash), total_fees=zero,
                   round_trip_reason=reason, limitations=LIMITATIONS, analysis=analysis,
                   risk=dict(policy_version='SPRINT09_V1', records=[], parameters=asdict(config.risk),
                             instrument_filters=wire(config.instrument_filters), evaluations=[], reservations=[],
                             protection_groups=[], equity_observations=[], blocks={}, execution_conventions=LIMITATIONS,
                             reconciliation=dict(status='NOT_APPLICABLE', reason=reason)))
    instrument_report(summary, session)
    return summary
