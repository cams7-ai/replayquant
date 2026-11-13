"""Coordenador schema 7: fronteiras atômicas, lotes e compromissos comuns.

Somente Candle encerrado e Opening são aceitos na API. O adaptador de arquivos
usa esta mesma fronteira; OHLC futuro nunca participa do dimensionamento.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256

from .catalog import minute
from .execution import effective_price, make_sma_fill
from .models import Candle, Opening, Request
from .portfolio import fill_movements
from .risk import EquityGuard
from .risk_models import RiskParameters
from .shared_config import SharedConfig
from .strategies import REGISTRY
from .metrics import ratio, percentage, seconds
from .reporting import canonical
from .validation import ValidationError, financial, identifier

ZERO = Decimal('0')
MINUTE = timedelta(minutes=1)
POLICIES = dict(signal='ALLOCATED_BUDGETS_V1', marks='BOUNDARY_MARKS_V1',
                gap='GLOBAL_GAP_INTERRUPT_V1', arbitration='PRIORITY_STRATEGY_SYMBOL_SIGNAL_V1',
                protection='STOP_FIRST', resolution='BAR_CLOSE_RESOLUTION', termination='KEEP_OPEN')


@dataclass(frozen=True)
class SharedRequest:
    id: str
    strategy_id: str
    symbol: str
    side: str
    lot_id: str | None = None
    target_order_id: str | None = None

    def __post_init__(self):
        for name in ('id', 'strategy_id', 'symbol'):
            identifier(getattr(self, name), name)
        if type(self.side) is not str or self.side not in ('BUY', 'SELL', 'CANCEL'):
            raise ValidationError('Ação exige BUY, SELL ou CANCEL')
        if self.lot_id is not None:
            identifier(self.lot_id, 'lot_id')
        if self.side == 'CANCEL':
            identifier(self.target_order_id, 'target_order_id')
        elif self.target_order_id is not None:
            raise ValidationError('Somente CANCEL aceita target_order_id')
        if self.side != 'SELL' and self.lot_id is not None:
            raise ValidationError('Somente SELL aceita lot_id')


class SharedSession:
    @financial
    def __init__(self, config, run_id='API'):
        if not isinstance(config, SharedConfig):
            raise ValidationError('API exige SharedConfig explícito')
        identifier(run_id, 'run_id')
        self.config, self.run_id = config, run_id
        self.owners = {s.id: s for s in config.strategies}
        self.cash = config.initial_cash
        self.initial = {s.id: config.initial_cash*s.allocation_fraction for s in config.strategies}
        self.initial['UNALLOCATED'] = self.cash-sum(self.initial.values(), ZERO)
        self.accounts = dict(self.initial)
        self.assets = {config.instrument(s).base_asset: ZERO for s, _ in config.instrument_limits}
        self.marks, self.lots, self.pending, self.reserves = {}, {}, {}, {}
        self.events, self.ledger, self.reservations, self.risk = [], [], [], []
        self.equity, self.contributions, self.exposure, self.fills, self.trades = [], [], [], [], []
        self.orders, self.requests, self.boundaries, self.last_exit = {}, {}, {}, {}
        self.indicators = {(s.id, symbol): REGISTRY.create(s.strategy, config.instrument(symbol).base_asset)
                           for s in config.strategies for symbol in s.symbols}
        self.evaluations, self.signals, self.decisions = [], [], []
        p = config.portfolio
        global_risk = RiskParameters(Decimal('1'), p.exposure_fraction, Decimal('0.5'), Decimal('1'),
                                     p.daily_loss_fraction, p.drawdown_fraction, p.max_price_age_seconds)
        self.guards = {'PORTFOLIO': EquityGuard(global_risk),
                       **{s.id: EquityGuard(s.risk) for s in config.strategies}}
        self.at, self.phase, self.seq = config.window.start, 'INITIAL', 0
        self.last_boundary, self.previous_openings = None, {}
        self.finished, self.interrupted, self.unavailable = False, False, False
        self.fees = self.slippage = ZERO
        self._ledger('INITIAL_BALANCE', 'PHYSICAL', 'UNALLOCATED', cash_delta=self.cash)
        self._ledger('INITIAL_BALANCE', 'ATTRIBUTION', 'UNALLOCATED', cash_delta=self.cash)
        for owner in sorted(self.owners):
            self._ledger('ALLOCATION', 'ATTRIBUTION', 'UNALLOCATED', cash_delta=-self.initial[owner])
            self._ledger('ALLOCATION', 'ATTRIBUTION', owner, cash_delta=self.initial[owner])
        self.observe('INITIAL')

    def emit(self, kind, **payload):
        self.seq += 1
        row = dict(schema_version=7, run_id=self.run_id, seq=self.seq, at=self.at,
                   phase=self.phase, type=kind, source=self.config.source,
                   interval=self.config.interval, quote_asset=self.config.quote_asset, **payload)
        self.events.append(row)
        return row

    def _ledger(self, kind, scope, owner, *, cash_delta=ZERO, asset_delta=ZERO, **payload):
        row = self.emit('LEDGER', entry_type=kind, account_scope=scope, strategy_id=owner,
                        cash_delta=cash_delta, asset_delta=asset_delta, **payload)
        self.ledger.append(row)

    def active_lots(self):
        return [x for x in self.lots.values() if x['status'] == 'OPEN']

    def own_lot(self, owner, symbol):
        return next((x for x in self.active_lots() if (x['strategy_id'], x['symbol']) == (owner, symbol)), None)

    def rank(self, owner, symbol, identity=''):
        return self.owners[owner].priority, owner, symbol, identity

    def lot_rank(self, lot):
        return self.rank(lot['strategy_id'], lot['symbol'], lot['lot_id'])

    def available(self, symbol, at):
        return (self.config.window.start <= at < self.config.window.end
                and self.config.instrument(symbol).contains(at, at+MINUTE))

    def reserved_cash(self, owner=None, exclude=None):
        return sum((x['amount'] for k, x in self.reserves.items() if k != exclude
                    and x['status'] == 'ACTIVE' and x['asset'] == 'USDT'
                    and (owner is None or x['strategy_id'] == owner)), ZERO)

    def equities(self):
        result = dict(self.accounts)
        for lot in self.active_lots():
            if lot['symbol'] not in self.marks:
                raise ValidationError('Posição sem marca aceita')
            result[lot['strategy_id']] += lot['quantity']*self.marks[lot['symbol']][0]
        return sum(result.values(), ZERO), result

    def commitments(self, owner=None, symbol=None, exclude=None):
        exposure = risk = ZERO
        for lot in self.active_lots():
            if (owner is None or lot['strategy_id'] == owner) and (symbol is None or lot['symbol'] == symbol):
                exposure += lot['quantity']*self.marks[lot['symbol']][0]
                risk += lot['planned_loss']
        for key, order in self.pending.items():
            if (key != exclude and order['side'] == 'BUY'
                    and (owner is None or order['strategy_id'] == owner)
                    and (symbol is None or order['symbol'] == symbol)):
                exposure += order['quantity']*order['entry']
                risk += order['planned_loss']
        return exposure, risk

    def reconcile(self):
        if self.cash != sum(self.accounts.values(), ZERO) or self.cash < 0:
            raise ValidationError('RECONCILIATION_FAILED: caixa atribuído')
        for asset, quantity in self.assets.items():
            lots = sum((x['quantity'] for x in self.active_lots() if x['base_asset'] == asset), ZERO)
            if lots != quantity or quantity < 0:
                raise ValidationError('RECONCILIATION_FAILED: lotes físicos')
            reserved = sum((r['amount'] for r in self.reserves.values()
                            if r['asset'] == asset and r['status'] == 'ACTIVE'), ZERO)
            if reserved > quantity:
                raise ValidationError('RECONCILIATION_FAILED: reserva base')
        if any(self.accounts[o] < self.reserved_cash(o) for o in self.accounts):
            raise ValidationError('RECONCILIATION_FAILED: orçamento reservado')
        physical_cash = sum((r['cash_delta'] for r in self.ledger if r['account_scope'] == 'PHYSICAL'), ZERO)
        if physical_cash != self.cash:
            raise ValidationError('RECONCILIATION_FAILED: ledger físico')
        for owner in self.accounts:
            reconstructed = sum((r['cash_delta'] for r in self.ledger
                                 if r['account_scope'] == 'ATTRIBUTION' and r['strategy_id'] == owner), ZERO)
            if reconstructed != self.accounts[owner]:
                raise ValidationError('RECONCILIATION_FAILED: ledger de atribuição')
        for asset, quantity in self.assets.items():
            reconstructed = sum((r['asset_delta'] for r in self.ledger
                                 if r['account_scope'] == 'PHYSICAL' and r.get('base_asset') == asset), ZERO)
            if reconstructed != quantity:
                raise ValidationError('RECONCILIATION_FAILED: ledger de ativos')
            for owner in self.owners:
                attributed = sum((r['asset_delta'] for r in self.ledger
                                  if r['account_scope'] == 'ATTRIBUTION' and r['strategy_id'] == owner
                                  and r.get('base_asset') == asset), ZERO)
                owned = sum((l['quantity'] for l in self.active_lots()
                             if l['strategy_id'] == owner and l['base_asset'] == asset), ZERO)
                if attributed != owned:
                    raise ValidationError('RECONCILIATION_FAILED: titularidade de ativos')
        return dict(status='PASSED', reconstructed_cash=self.cash, assets=dict(self.assets))

    def observe(self, reason):
        self.reconcile()
        total, parts = self.equities()
        committed, planned = self.commitments()
        row = self.emit('EQUITY', reason=reason, cash_total=self.cash,
                        cash_reserved=self.reserved_cash(), cash_available=self.cash-self.reserved_cash(),
                        gross_equity=total, paid_fees=self.fees, committed_exposure=committed,
                        open_planned_risk=planned,
                        exposure_excess=max(ZERO, committed-total*self.config.portfolio.exposure_fraction),
                        open_risk_excess=max(ZERO, planned-total*self.config.portfolio.max_open_risk_fraction),
                        hypothetical_liquidation_equity=self.cash+sum(
                            (l['quantity']*self.marks[l['symbol']][0]*(1-self.config.slippage_rate)*(1-self.config.fee_rate)
                             for l in self.active_lots()), ZERO), assets=dict(self.assets))
        self.equity.append(row)
        for owner, guard in self.guards.items():
            value = total if owner == 'PORTFOLIO' else parts[owner]
            self.guards[owner] = guard.observe(self.at, row['seq'], self.phase, value)
            self.risk.append(dict(schema_version=7, run_id=self.run_id, record_type='GUARD', strategy_id=owner,
                                  **self.guards[owner].current))
        for owner in sorted(self.owners):
            realized = sum((t['net_pnl'] for t in self.trades if t['strategy_id'] == owner), ZERO)
            pnl = parts[owner]-self.initial[owner]
            self.contributions.append(dict(seq=row['seq'], at=self.at, phase=self.phase, strategy_id=owner,
                                           initial_allocation=self.initial[owner], cash_total=self.accounts[owner],
                                           cash_reserved=self.reserved_cash(owner), equity=parts[owner], pnl=pnl,
                                           realized_pnl=realized, unrealized_pnl=pnl-realized,
                                           contribution_pct=percentage(pnl, self.config.initial_cash),
                                           own_return_pct=percentage(pnl, self.initial[owner])))
            for symbol in self.owners[owner].symbols:
                x, k = self.commitments(owner, symbol)
                position = sum((l['quantity']*self.marks[symbol][0] for l in self.active_lots()
                                if l['strategy_id'] == owner and l['symbol'] == symbol), ZERO)
                self.exposure.append(dict(seq=row['seq'], at=self.at, phase=self.phase, strategy_id=owner,
                                          symbol=symbol, base_asset=self.config.instrument(symbol).base_asset,
                                          position_notional=position, committed_exposure=x, planned_loss=k,
                                          portfolio_fraction=ratio(Fraction(x)/Fraction(total), 'FRACTION') if total else None))

    def reserve(self, identity, owner, symbol, amount, asset, holder, lot_id=None):
        if identity in self.reserves:
            raise ValidationError('Reserva duplicada')
        self.reserves[identity] = dict(reservation_id=identity, strategy_id=owner, symbol=symbol, amount=amount,
                                       asset=asset, holder=holder, lot_id=lot_id, status='ACTIVE')
        self.reservation_event(identity, 'CREATED')

    def reservation_event(self, identity, action, holder=None):
        reserve = self.reserves[identity]
        if holder is not None:
            reserve['holder'] = holder
        if action in ('RELEASED', 'CONSUMED'):
            reserve['status'] = action
        self.reservations.append(self.emit('RESERVATION', action=action, **deepcopy(reserve)))
        self.observe('RESERVATION_'+action)

    def buy_reason(self, owner, symbol, *, exclude=None, reservation_id=None, check_position=True):
        if not self.config.instrument(symbol).contains(self.at, self.at+MINUTE):
            return 'INSTRUMENT_UNAVAILABLE'
        for scope, prefix in (('PORTFOLIO', 'PORTFOLIO'), (owner, 'STRATEGY')):
            state = self.guards[scope].current
            if state['daily_blocked']:
                return prefix+'_DAILY_LOSS_BLOCKED'
            if state['drawdown_blocked']:
                return prefix+'_DRAWDOWN_BLOCKED'
        mark = self.marks.get(symbol)
        if mark is None:
            return 'PRICE_MISSING'
        if mark[1] > self.at:
            raise ValidationError('Preço futuro')
        if seconds(mark[1], self.at) > self.owners[owner].risk.max_price_age_seconds:
            return 'PRICE_STALE'
        for lot in self.active_lots():
            held = self.marks.get(lot['symbol'])
            if held is None:
                return 'PORTFOLIO_PRICE_MISSING'
            if held[1] > self.at:
                raise ValidationError('Preço futuro')
            if seconds(held[1], self.at) > self.config.portfolio.max_price_age_seconds:
                return 'PORTFOLIO_PRICE_STALE'
        if any(k != exclude and (p['strategy_id'], p['symbol']) == (owner, symbol) for k, p in self.pending.items()):
            return 'ORDER_PENDING'
        if check_position and self.own_lot(owner, symbol):
            return 'POSITION_OPEN'
        candle_start = self.at if self.phase == 'BUY_FILL' else self.at-MINUTE
        if self.last_exit.get((owner, symbol)) == candle_start:
            return 'REENTRY_SAME_CANDLE'
        total, parts = self.equities()
        if total <= 0 or parts[owner] <= 0:
            return 'NON_POSITIVE_EQUITY'
        if min(self.cash-self.reserved_cash(exclude=reservation_id),
               self.accounts[owner]-self.reserved_cash(owner, reservation_id)) <= 0:
            return 'INSUFFICIENT_CASH'
        return None

    def size(self, owner, symbol):
        c, r = self.config, self.owners[owner].risk
        total, parts = self.equities()
        entry = effective_price(self.marks[symbol][0], 'BUY', c.slippage_rate)
        stop, target = entry*(1-r.stop_fraction), entry*(1+r.target_fraction)
        loss = entry*(1+c.fee_rate)-stop*(1-c.fee_rate)
        budget = parts[owner]*r.risk_fraction
        x, k = self.commitments()
        xs, _ = self.commitments(owner=owner)
        xi, _ = self.commitments(symbol=symbol)
        candidates = dict(risk_strategy=Fraction(budget)/Fraction(loss),
                          risk_portfolio=Fraction(max(ZERO, total*c.portfolio.max_open_risk_fraction-k))/Fraction(loss),
                          exposure_portfolio=Fraction(max(ZERO, total*c.portfolio.exposure_fraction-x))/Fraction(entry),
                          exposure_instrument=Fraction(max(ZERO, total*dict(c.instrument_limits)[symbol]-xi))/Fraction(entry),
                          exposure_strategy=Fraction(max(ZERO, parts[owner]*r.exposure_fraction-xs))/Fraction(entry),
                          cash=Fraction(min(self.cash-self.reserved_cash(), self.accounts[owner]-self.reserved_cash(owner)))/Fraction(entry*(1+c.fee_rate)))
        raw = min(candidates.values())
        q = Decimal(raw//Fraction(c.instrument(symbol).instrument_filters.step))*c.instrument(symbol).instrument_filters.step
        return dict(entry=entry, stop=stop, target=target, budget=budget, quantity=q,
                    planned_loss=q*loss, outlay=q*entry*(1+c.fee_rate),
                    candidates={k: ratio(v, c.instrument(symbol).base_asset) for k, v in candidates.items()},
                    limiters=sorted(k for k, v in candidates.items() if v == raw))

    def minimums(self, symbol, q, entry):
        f = self.config.instrument(symbol).instrument_filters
        return q > 0 and q >= f.min_quantity and q*entry >= f.min_notional

    def decision(self, request, reason, sizing=None):
        row = self.emit('DECISION', signal_id=request.id, strategy_id=request.strategy_id,
                        symbol=request.symbol, side=request.side, approved=reason is None, reason=reason, sizing=sizing,
                        active_blocks={k: {n: g.current[n] for n in ('daily_blocked', 'drawdown_blocked')}
                                       for k, g in self.guards.items() if k in ('PORTFOLIO', request.strategy_id)})
        self.decisions.append(row)
        self.risk.append(dict(row, record_type='DECISION'))

    def process_request(self, request):
        owner, symbol = request.strategy_id, request.symbol
        if owner not in self.owners or (owner, symbol) not in self.indicators:
            raise ValidationError('Binding inexistente')
        key = owner+':'+symbol+':'+request.id
        if key in self.requests:
            if self.requests[key] != request:
                raise ValidationError('Ação conflitante')
            return
        self.requests[key] = request
        if request.side == 'CANCEL':
            target = self.pending.get(request.target_order_id)
            reason = None if target else 'ORDER_NOT_PENDING'
            if target and (target['strategy_id'], target['symbol']) != (owner, symbol):
                reason = 'OWNERSHIP_MISMATCH'
            self.decision(request, reason)
            if reason is None:
                self.cancel(target, 'CANCELLED')
            return
        if request.side == 'SELL':
            lot = self.lots.get(request.lot_id) if request.lot_id else self.own_lot(owner, symbol)
            reason = None
            if lot and (lot['strategy_id'], lot['symbol']) != (owner, symbol):
                reason = 'OWNERSHIP_MISMATCH'
            elif not lot or lot['status'] != 'OPEN':
                reason = 'INSUFFICIENT_ASSET'
            elif not self.config.instrument(symbol).contains(self.at, self.at+MINUTE):
                reason = 'INSTRUMENT_UNAVAILABLE'
            elif any((p['strategy_id'], p['symbol']) == (owner, symbol) for p in self.pending.values()):
                reason = 'ORDER_PENDING'
            self.decision(request, reason)
            if reason:
                return
            order = dict(order_id=key, strategy_id=owner, symbol=symbol, side='SELL', lot_id=lot['lot_id'],
                         reservation_id=lot['reservation_id'], quantity=lot['quantity'], status='PENDING', submitted_at=self.at)
            self.orders[key] = order
            self.pending[key] = order
            self.reservation_event(lot['reservation_id'], 'TRANSFERRED', key)
            return
        reason = self.buy_reason(owner, symbol)
        sizing = None
        if reason is None:
            sizing = self.size(owner, symbol)
            if not self.minimums(symbol, sizing['quantity'], sizing['entry']):
                reason = 'BELOW_MINIMUMS'
        self.decision(request, reason, sizing)
        if reason:
            return
        order = dict(order_id=key, strategy_id=owner, symbol=symbol, side='BUY', status='PENDING',
                     submitted_at=self.at, reservation_id=key+':USDT', **sizing)
        self.orders[key] = order
        self.pending[key] = order
        self.reserve(order['reservation_id'], owner, symbol, order['outlay'], 'USDT', key)

    def cancel(self, order, reason):
        self.pending.pop(order['order_id'])
        order.update(status='CANCELLED' if reason == 'CANCELLED' else 'UNEXECUTED', reason=reason)
        if order['side'] == 'BUY':
            self.reservation_event(order['reservation_id'], 'RELEASED')
        else:
            lot = self.lots[order['lot_id']]
            self.reservation_event(order['reservation_id'], 'TRANSFERRED', lot['lot_id']+':protection')
        self.emit(order['status'], order_id=order['order_id'], strategy_id=order['strategy_id'], reason=reason)

    def revalidate(self, order, opening):
        owner, symbol, key = order['strategy_id'], order['symbol'], order['order_id']
        reason = self.buy_reason(owner, symbol, exclude=key, reservation_id=order['reservation_id'])
        c, q = self.config, order['quantity']
        entry = effective_price(opening.price, 'BUY', c.slippage_rate)
        loss = q*(entry*(1+c.fee_rate)-order['stop']*(1-c.fee_rate))
        outlay = q*entry*(1+c.fee_rate)
        total, parts = self.equities()
        x, k = self.commitments(exclude=key)
        xi, _ = self.commitments(symbol=symbol, exclude=key)
        xs, _ = self.commitments(owner=owner, exclude=key)
        checks = [('ENTRY_OUTSIDE_BRACKET', not order['stop'] < entry < order['target']),
                  ('RISK_BUDGET_EXCEEDED', loss > order['budget']),
                  ('INSUFFICIENT_CASH', outlay > min(self.cash-self.reserved_cash(exclude=order['reservation_id']),
                                                    self.accounts[owner]-self.reserved_cash(owner, order['reservation_id']))),
                  ('EXPOSURE_PORTFOLIO', x+q*entry > total*c.portfolio.exposure_fraction),
                  ('EXPOSURE_INSTRUMENT', xi+q*entry > total*dict(c.instrument_limits)[symbol]),
                  ('EXPOSURE_STRATEGY', xs+q*entry > parts[owner]*self.owners[owner].risk.exposure_fraction),
                  ('OPEN_RISK_LIMIT', k+loss > total*c.portfolio.max_open_risk_fraction),
                  ('BELOW_MINIMUMS', not self.minimums(symbol, q, entry))]
        reason = reason or next((name for name, failed in checks if failed), None)
        self.risk.append(self.emit('REVALIDATION', record_type='REVALIDATION', order_id=key, strategy_id=owner,
                                   reason=reason, entry=entry, planned_loss=loss, outlay=outlay,
                                   equity=total, own_equity=parts[owner], exposure_without_self=x,
                                   instrument_without_self=xi, strategy_without_self=xs, risk_without_self=k))
        return reason, loss

    def fill(self, order, reference, *, lot=None, reason=None, planned_loss=None):
        c, owner, symbol = self.config, order['strategy_id'], order['symbol']
        request = Request(order['order_id'], self.at, order['side'])
        opening = Opening(c.source, symbol, c.interval, self.at, reference)
        execution = make_sma_fill(request, opening, order['quantity'], c.fee_rate, c.slippage_rate)
        buy = order['side'] == 'BUY'
        gross, cash_delta, asset_delta = fill_movements(execution)
        base = c.instrument(symbol).base_asset
        if buy:
            lot_id = execution.id+':lot'
            lot = dict(lot_id=lot_id, strategy_id=owner, symbol=symbol, base_asset=base,
                       quantity=execution.quantity, entry_fill=execution.id, entry_order=order['order_id'],
                       entry_at=self.at, entry_reference=reference, entry_price=execution.price,
                       entry_fee=execution.fee, cost_basis=gross+execution.fee, stop=order['stop'], target=order['target'],
                       planned_loss=planned_loss, initial_planned_loss=order['planned_loss'], status='OPEN',
                       reservation_id=lot_id+':base', protection_status='ACTIVE')
            self.lots[lot_id] = lot
        else:
            if not lot or lot['strategy_id'] != owner or lot['symbol'] != symbol or lot['status'] != 'OPEN':
                raise ValidationError('OWNERSHIP_MISMATCH')
            if execution.quantity != lot['quantity']:
                raise ValidationError('Venda exige quantidade integral do lote')
            lot_id = lot['lot_id']
            lot.update(status='CLOSED', exit_at=self.at, exit_fill=execution.id, exit_reason=reason or 'SIGNAL',
                       realized_pnl=cash_delta-lot['cost_basis'], protection_status='CLOSED')
            self.last_exit[owner, symbol] = self.at-MINUTE if self.phase == 'OHLC_PROTECTION' else self.at
            self.trades.append(dict(trade_id=lot_id+':trade', lot_id=lot_id, strategy_id=owner, symbol=symbol,
                                    quantity=execution.quantity, buy_at=lot['entry_at'], sell_at=self.at,
                                    cash_outflow=lot['cost_basis'], cash_inflow=cash_delta, net_pnl=lot['realized_pnl'],
                                    buy_fee=lot['entry_fee'], sell_fee=execution.fee,
                                    duration_seconds=int((self.at-lot['entry_at']).total_seconds()), reason=reason or 'SIGNAL'))
        self.cash += cash_delta
        self.accounts[owner] += cash_delta
        self.assets[base] += asset_delta
        self.fees += execution.fee
        self.slippage += abs(execution.price-reference)*execution.quantity
        # Remover o compromisso antes de reconciliar o fill; a reserva base é criada depois.
        self.pending.pop(order['order_id'], None)
        reserve = self.reserves[order['reservation_id']]
        reserve['status'] = 'CONSUMED'
        order['status'] = 'FILLED'
        row = self.emit('FILL', strategy_id=owner, symbol=symbol, base_asset=base,
                        lot_id=lot_id, order_id=order['order_id'], fill_id=execution.id, side=execution.side,
                        quantity=execution.quantity, reference_price=reference, effective_price=execution.price,
                        gross=gross, fee=execution.fee, reason=reason, cash_delta=cash_delta, asset_delta=asset_delta)
        self.fills.append(row)
        for scope in ('PHYSICAL', 'ATTRIBUTION'):
            self._ledger('FILL', scope, owner, transaction_id=execution.id, lot_id=lot_id,
                         symbol=symbol, base_asset=base, order_id=order['order_id'], fill_id=execution.id,
                         side=execution.side, quantity=execution.quantity, reference_price=reference,
                         effective_price=execution.price, gross=gross, fee=execution.fee,
                         cash_delta=cash_delta, asset_delta=asset_delta)
        reserve['lot_id'] = lot_id
        self.reservation_event(order['reservation_id'], 'CONSUMED')
        self.observe('FILL')
        if buy:
            self.reserve(lot['reservation_id'], owner, symbol, lot['quantity'], base, lot_id+':protection', lot_id)

    def protective_exit(self, lot, reference, reason):
        for order in list(self.pending.values()):
            if order.get('lot_id') == lot['lot_id']:
                self.cancel(order, 'PROTECTION_PREEMPTED')
        key = lot['lot_id']+':'+reason
        order = dict(order_id=key, strategy_id=lot['strategy_id'], symbol=lot['symbol'], side='SELL',
                     quantity=lot['quantity'], reservation_id=lot['reservation_id'])
        self.orders[key] = order
        self.reservation_event(lot['reservation_id'], 'TRANSFERRED', key)
        self.fill(order, reference, lot=lot, reason=reason)

    def _normalize(self, values, model, at):
        if type(values) not in (list, tuple):
            raise ValidationError('Lote exige lista/tupla tipada')
        result = {}
        for value in values:
            if not isinstance(value, model):
                raise ValidationError('Tipo de evento inválido')
            # Equivalência numérica também é equivalência de digest, sem depender
            # da ordem de duplicatas com escalas decimais diferentes.
            decimal_fields = ('open', 'high', 'low', 'close', 'volume') if model is Candle else ('price',)
            def normalized(number):
                text = format(number, 'f')
                if '.' in text:
                    text = text.rstrip('0').rstrip('.')
                return Decimal(text) if number else ZERO
            value = replace(value, **{k: normalized(getattr(value, k)) for k in decimal_fields})
            symbol = value.symbol
            if (value.source, value.interval) != (self.config.source, self.config.interval) or symbol not in dict(self.config.instrument_limits):
                raise ValidationError('Evento estrangeiro')
            if self.config.source == 'BINANCE_SPOT':
                provenance = next(p for p in self.config.provenance if symbol+'.json' in dict(p.files))
                provenance.verify_event(value)
            timestamp = value.close_time if model is Candle else value.at
            if timestamp != at:
                raise ValidationError('Evento fora da fronteira')
            start = value.open_time if model is Candle else value.at
            if not self.available(symbol, start):
                raise ValidationError('Evento fora da disponibilidade/janela')
            if symbol in result and result[symbol] != value:
                raise ValidationError('Evento conflitante')
            result[symbol] = value
        return result

    @financial
    def on_boundary(self, at, closes=(), openings=(), requests=()):
        at = minute(at)
        close_map = self._normalize(closes, Candle, at)
        open_map = self._normalize(openings, Opening, at)
        if type(requests) not in (list, tuple) or not all(isinstance(r, SharedRequest) for r in requests):
            raise ValidationError('Ações exigem SharedRequest')
        request_map = {}
        for r in requests:
            if (r.strategy_id, r.symbol) not in self.indicators:
                raise ValidationError('Binding inexistente')
            key = r.strategy_id, r.symbol, r.id
            if key in request_map and request_map[key] != r:
                raise ValidationError('Ação duplicada conflitante')
            request_map[key] = r
        digest = sha256(canonical(dict(at=at, closes=sorted(close_map.items()), openings=sorted(open_map.items()),
                                       requests=sorted(request_map.items())))).hexdigest()
        if at in self.boundaries:
            if self.boundaries[at] != digest:
                raise ValidationError('Fronteira conflitante')
            return self
        if self.finished or self.interrupted:
            raise ValidationError('Sessão encerrada')
        expected = self.config.window.start if self.last_boundary is None else self.last_boundary+MINUTE
        if at != expected or at > self.config.window.end:
            raise ValidationError('Fronteira fora de ordem')
        if set(close_map) != set(self.previous_openings):
            raise ValidationError('Fechamentos devem corresponder às aberturas aceitas')
        for symbol, close in close_map.items():
            if close.opening() != self.previous_openings[symbol]:
                raise ValidationError('Fechamento diverge da abertura aceita')
        candidate = deepcopy(self)
        candidate._boundary(at, close_map, open_map, list(request_map.values()), digest)
        self.__dict__.clear()
        self.__dict__.update(candidate.__dict__)
        return self

    def enter_phase(self, phase):
        self.phase = phase
        self.emit('PHASE_STARTED')

    def _boundary(self, at, closes, openings, requests, digest):
        self.at, self.phase = at, 'CLOSE_MARKS'
        self.emit('BOUNDARY', boundary_id=at.isoformat(), digest=digest)
        self.marks.update({s: (c.close, at) for s, c in closes.items()})
        self.emit('MARK_BATCH', marks={s: c.close for s, c in sorted(closes.items())})
        self.observe('CLOSE_MARKS')
        self.enter_phase('OHLC_PROTECTION')
        for lot in sorted(self.active_lots(), key=self.lot_rank):
            candle = closes.get(lot['symbol'])
            if candle is None or candle.open_time <= lot['entry_at'] or lot['protection_status'] != 'ACTIVE':
                continue
            stop, target = candle.low <= lot['stop'], candle.high >= lot['target']
            if stop or target:
                self.emit('PROTECTIVE_TRIGGER', lot_id=lot['lot_id'], ambiguous=stop and target,
                          resolution='BAR_CLOSE_RESOLUTION')
                self.protective_exit(lot, lot['stop'] if stop else lot['target'], 'STOP' if stop else 'TARGET')
        self.enter_phase('SIGNALS')
        for (owner, symbol), indicator in sorted(self.indicators.items()):
            if symbol not in closes:
                continue
            evaluation = indicator.on_close(closes[symbol])
            identity = f'{owner}:{symbol}:{at.isoformat()}'
            evaluation = self.emit('EVALUATION', evaluation_id=identity+':evaluation', strategy_id=owner,
                                   symbol=symbol, evaluation=evaluation)
            self.evaluations.append(evaluation)
            side = evaluation['evaluation']['side']
            if side:
                request = SharedRequest(identity+':signal', owner, symbol, side)
                self.signals.append(self.emit('SIGNAL', signal_id=request.id, strategy_id=owner, symbol=symbol, side=side))
                requests.append(request)
        self.enter_phase('SELL_REQUESTS')
        for request in sorted((r for r in requests if r.side != 'BUY'), key=lambda r: self.rank(r.strategy_id, r.symbol, r.id)):
            self.process_request(request)
        self.enter_phase('BUY_ARBITRATION')
        for request in sorted((r for r in requests if r.side == 'BUY'), key=lambda r: self.rank(r.strategy_id, r.symbol, r.id)):
            self.process_request(request)
        self.enter_phase('OPEN_VALIDATION')
        expected = {s for s, _ in self.config.instrument_limits if self.available(s, at)}
        missing = expected-set(openings)
        if missing:
            self.interrupted = True
            self.emit('INTERRUPTED', reason='DATA_GAP', missing_symbols=sorted(missing))
        else:
            self.enter_phase('OPEN_MARKS')
            self.marks.update({s: (o.price, at) for s, o in openings.items()})
            if openings:
                self.emit('MARK_BATCH', marks={s: o.price for s, o in sorted(openings.items())})
                self.observe('OPEN_MARKS')
            self.enter_phase('GAP_PROTECTION')
            for lot in sorted(self.active_lots(), key=self.lot_rank):
                opening = openings.get(lot['symbol'])
                if opening is None or opening.at <= lot['entry_at'] or lot['protection_status'] != 'ACTIVE':
                    continue
                if opening.price <= lot['stop'] or opening.price >= lot['target']:
                    self.protective_exit(lot, opening.price, 'GAP_STOP' if opening.price <= lot['stop'] else 'GAP_TARGET')
            self.enter_phase('SELL_FILL')
            for order in sorted(list(self.pending.values()), key=lambda o: self.rank(o['strategy_id'], o['symbol'], o['order_id'])):
                if order['side'] == 'SELL' and order['symbol'] in openings:
                    self.fill(order, openings[order['symbol']].price, lot=self.lots[order['lot_id']])
            self.enter_phase('BUY_FILL')
            for order in sorted(list(self.pending.values()), key=lambda o: self.rank(o['strategy_id'], o['symbol'], o['order_id'])):
                if order['side'] != 'BUY' or order['symbol'] not in openings:
                    continue
                reason, loss = self.revalidate(order, openings[order['symbol']])
                if reason:
                    self.pending.pop(order['order_id'])
                    order.update(status='REJECTED', reason=reason)
                    self.emit('REJECTED', order_id=order['order_id'], strategy_id=order['strategy_id'], reason=reason)
                    self.reservation_event(order['reservation_id'], 'RELEASED')
                else:
                    self.fill(order, openings[order['symbol']].price, planned_loss=loss)
            self.enter_phase('AVAILABILITY')
            for order in list(self.pending.values()):
                if not self.available(order['symbol'], at) and at < self.config.window.end:
                    self.cancel(order, 'INSTRUMENT_UNAVAILABLE')
            for lot in self.active_lots():
                if not self.available(lot['symbol'], at) and at < self.config.window.end and lot['protection_status'] == 'ACTIVE':
                    lot['protection_status'] = 'INSTRUMENT_UNAVAILABLE'
                    self.reservation_event(lot['reservation_id'], 'RELEASED')
                    self.emit('PROTECTION_UNAVAILABLE', lot_id=lot['lot_id'], reason='INSTRUMENT_UNAVAILABLE')
        self.boundaries[at] = digest
        self.last_boundary = at
        if not self.interrupted:
            self.previous_openings = dict(openings)

    @financial
    def finish(self, *, unavailable=False):
        if type(unavailable) is not bool:
            raise ValidationError('unavailable exige booleano')
        if self.finished:
            return self
        if unavailable and (self.last_boundary is not None or self.marks or self.pending or self.fills):
            raise ValidationError('Indisponibilidade total exige sessão sem observações')
        if not self.interrupted and not unavailable and (self.last_boundary != self.config.window.end or self.previous_openings):
            raise ValidationError('Finalização exige última fronteira fechada')
        candidate = deepcopy(self)
        candidate.phase = 'TERMINAL'
        candidate.unavailable = unavailable
        if not candidate.interrupted:
            for order in list(candidate.pending.values()):
                candidate.cancel(order, 'NO_FUTURE_OPEN')
            for reserve in candidate.reserves.values():
                if reserve['status'] == 'ACTIVE':
                    candidate.reservation_event(reserve['reservation_id'], 'RELEASED')
            for lot in candidate.active_lots():
                if lot['protection_status'] == 'ACTIVE':
                    lot['protection_status'] = 'NO_FUTURE_OPEN'
        candidate.observe('TERMINAL')
        candidate.finished = True
        self.__dict__.clear()
        self.__dict__.update(candidate.__dict__)
        return self

    @property
    def exit_code(self):
        if self.interrupted:
            return 1
        if (self.unavailable or any(not d['approved'] for d in self.decisions)
                or any(o.get('status') in ('REJECTED', 'UNEXECUTED') and o.get('reason') != 'PROTECTION_PREEMPTED'
                       for o in self.orders.values())):
            return 2
        return 0


def replay_shared(inputs, run_id='API'):
    session = SharedSession(inputs.config, run_id)
    streams = dict(inputs.datasets)
    if not any(streams.values()):
        session.finish(unavailable=True)
        return session
    opens = {s: {c.open_time: c.opening() for c in candles} for s, candles in streams.items()}
    closes = {s: {c.close_time: c for c in candles} for s, candles in streams.items()}
    at = inputs.config.window.start
    while at <= inputs.config.window.end:
        session.on_boundary(at, [v[at] for v in closes.values() if at in v],
                            [v[at] for v in opens.values() if at in v])
        if session.interrupted:
            break
        at += MINUTE
    return session.finish()
