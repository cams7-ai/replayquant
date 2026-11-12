"""Extensão da sessão existente: risco, reservas e coordenação de saídas totais."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from .data import validate_series
from .engine import Session
from .execution import effective_price
from .models import Candle, Fill, Opening
from .protection import Protection, opening_trigger, range_trigger
from .reservations import Reservation, ReservationLedger
from .risk import EquityGuard, RiskSnapshot, evaluate, revalidate, POLICY
from .risk_models import RiskConfig, RiskOrder, RiskRequest
from .strategies import SMACross, REGISTRY
from .validation import ValidationError, financial, identifier

ZERO = Decimal('0')


def atomic(function):
    """Preparar o evento completo em estado isolado e comprometer só no sucesso."""
    @wraps(function)
    @financial
    def wrapped(self, *args, **kwargs):
        candidate = deepcopy(self)
        result = function(candidate, *args, **kwargs)
        self.__dict__.update(candidate.__dict__)
        return deepcopy(result)
    return wrapped


class RiskSession(Session):
    def __init__(self, config, run_id='api'):
        if not isinstance(config, RiskConfig):
            raise ValidationError('RiskSession exige RiskConfig')
        super().__init__(config, run_id)
        self._ledger = ReservationLedger.initial(config.initial_cash, run_id, base_asset=getattr(config, 'base_asset', None))
        self._guard = EquityGuard(config.risk)
        self.strategy = None
        if config.mode == 'SMA':
            self.strategy = SMACross(config.strategy)
        elif config.mode == 'STRATEGY':
            self.strategy = REGISTRY.create(config.strategy, getattr(config, 'base_asset', 'BTC'))
        self.status, self.diagnostic = 'RUNNING', None
        self._mark = self._mark_at = None
        self._group = None
        self._groups = ()
        self._risk_records = []
        self._actions = {}
        self._seen_opens, self._seen_candles, self._signals = {}, {}, {}
        self._source_candles = ()
        self._input_diagnostics = ()
        self._last_exit_candle = None
        self._eligible = None

    @property
    def guard(self):
        return deepcopy(self._guard)

    @property
    def ledger(self):
        return deepcopy(self._ledger)

    @property
    def orders(self):
        return deepcopy(super().orders)

    @property
    def risk_records(self):
        return deepcopy(self._risk_records)

    @property
    def protection_groups(self):
        return deepcopy((*self._groups, *((self._group,) if self._group else ())))

    def _emit(self, at, event_type, **payload):
        super()._emit(at, event_type, **payload)
        self._events[-1]['schema_version'] = self.config.schema_version

    def _validate_market_event(self, event):
        if (event.source, event.symbol, event.interval) != (self.config.source, self.config.symbol, self.config.interval):
            raise ValidationError('Evento de instrumento divergente')
        if self.config.schema_version == 6:
            from .models import Opening
            opening = event.at if isinstance(event, Opening) else event.open_time
            closing = opening + timedelta(minutes=1)
            if not self.config.instrument.contains(opening, closing):
                raise ValidationError('INSTRUMENT_UNAVAILABLE')
            if not self.config.window.contains(opening, closing):
                raise ValidationError('OUTSIDE_WINDOW')

    def _active(self):
        if self.status == 'INTERRUPTED':
            raise ValidationError('Sessão interrompida; iniciar nova execução')
        super()._active()

    def _record(self, kind, at, seq, payload):
        self._risk_records.append(dict(schema_version=self.config.schema_version, run_id=self.run_id,
                                       record_type=kind, at=at, source_event_seq=seq,
                                       payload=deepcopy(payload)))

    @financial
    def _observe(self, at, phase):
        equity = self.balance.cash + (self.balance.asset_quantity*self._mark if self.balance.asset_quantity else ZERO)
        seq = len(self._events)
        guard = self._guard.observe(at, seq, phase, equity)
        if len(guard.history) != len(self._guard.history):
            self._record('EQUITY_OBSERVATION', at, seq, guard.current)
        self._guard = guard

    @financial
    def snapshot(self, at, *, own_reserve=ZERO):
        current = self._guard.current or {}
        balance = self._ledger.entries[-1]
        exposure = self.balance.asset_quantity*self._mark if self.balance.asset_quantity else ZERO
        return RiskSnapshot(self.balance.cash+exposure, balance.cash_available_after+own_reserve,
                            exposure, self._mark, self._mark_at, at, self.pending is not None,
                            self.balance.asset_quantity != 0, self._opening is not None and self._last_exit_candle == self._opening.at,
                            current.get('daily_blocked', False), current.get('drawdown_blocked', False))

    def _adjust(self, kind, at, operations):
        seq = len(self._events)+1
        operation_id = f'reservation-event:{seq}'
        prepared = self._ledger.adjust(kind, operation_id, at, seq, tuple(operations))
        self._ledger = prepared
        self._emit(at, kind, ledger_id=prepared.entries[-1].ledger_id, operations=tuple(operations))
        self._observe(at, kind)

    def _cash_reservation(self, order_id):
        return self._ledger.held(f'{order_id}:cash')

    def _asset_reservation(self):
        if self._group is None:
            raise ValidationError('Posição sem grupo protetivo')
        return self._ledger.held(f'{self._group.id}:asset')

    def _phase_close(self, request):
        if (self._closed is None or self._opening.at != self._closed.open_time
                or request.at_close != self._closed.close_time):
            raise ValidationError('Ação exige fase do fechamento indicado')

    @atomic
    def submit(self, request):
        if not isinstance(request, RiskRequest):
            raise ValidationError('Modo risco exige RiskRequest')
        strategy_cancel = self.config.mode == 'STRATEGY' and request.side == 'CANCEL'
        if self.config.mode != 'MANUAL' and request.id not in self._actions and not strategy_cancel:
            raise ValidationError('Estratégia exige handle_signal')
        return self._submit(request)

    def _submit(self, request):
        if request.id in self._actions:
            if self._actions[request.id] != request:
                raise ValidationError('ID de ação conflitante')
            return self._orders[request.id]
        self._active()
        self._phase_close(request)
        if request.side == 'CANCEL':
            return self._cancel_action(request)
        sizing = None
        if request.side == 'BUY':
            decision = evaluate(self.config, self.snapshot(request.at_close))
            reason, q, sizing = decision['reason'], decision['approved_quantity'], decision['sizing']
        else:
            reason = ('ORDER_PENDING' if self.pending else
                      ('INSUFFICIENT_ASSET' if self.balance.asset_quantity == 0 else None))
            q = self.balance.asset_quantity if reason is None else ZERO
            decision = dict(approved=reason is None, reason=reason, approved_quantity=q, snapshot=self.snapshot(request.at_close),
                            sizing=None, sizing_reason='EXIT_NOT_SIZED')
        self._emit(request.at_close, 'SUBMITTED', order_id=request.id, side=request.side, quantity=q)
        self._emit(request.at_close, 'RISK_EVALUATION', order_id=request.id, **decision)
        self._record('EVALUATION', request.at_close, len(self._events), dict(order_id=request.id, **decision))
        order = RiskOrder(request, 'REJECTED' if reason else 'NEW', len(self._events), reason, q, sizing)
        self._orders[request.id], self._actions[request.id] = order, request
        self._emit(request.at_close, 'REJECTED' if reason else 'ACCEPTED', order_id=request.id,
                   status=order.status, reason=reason)
        if reason is None:
            self._pending = request.id
            if request.side == 'BUY':
                self._adjust('RESERVE', request.at_close,
                             [Reservation(f'{request.id}:cash', request.id, 'USDT', sizing['outlay'])])
            else:
                self._adjust('TRANSFER', request.at_close,
                             [replace(self._asset_reservation(), owner_id=request.id)])
        return order

    def _cancel_order(self, order_id, at, status, reason):
        order = self._orders[order_id]
        if order.status != 'NEW' or self.pending != order_id:
            raise ValidationError('ORDER_NOT_PENDING')
        if order.request.side == 'BUY':
            self._adjust('RELEASE', at, [replace(self._cash_reservation(order_id), status='RELEASED')])
        else:
            self._adjust('TRANSFER', at, [replace(self._asset_reservation(), owner_id=self._group.id)])
        self._orders[order_id] = replace(order, status=status, reason=reason)
        self._pending = None
        self._emit(at, status, order_id=order_id, status=status, reason=reason)

    def _cancel_action(self, request):
        target = self._orders.get(request.target_order_id)
        reason = None if target and target.status == 'NEW' and self.pending == target.request.id else 'ORDER_NOT_PENDING'
        if reason is None:
            self._cancel_order(target.request.id, request.at_close, 'CANCELED', 'MANUAL_CANCEL')
        action = RiskOrder(request, 'REJECTED' if reason else 'CANCELED', len(self._events), reason or 'MANUAL_CANCEL')
        self._actions[request.id], self._orders[request.id] = request, action
        self._emit(request.at_close, action.status, order_id=request.id,
                   target_order_id=request.target_order_id, status=action.status, reason=action.reason)
        return action

    @atomic
    def handle_signal(self, signal_id, side, at, evaluation_id=None):
        identifier(signal_id)
        if self.config.mode == 'MANUAL':
            raise ValidationError('Sinais exigem modo de estratégia')
        request = RiskRequest(f'{signal_id}:order', at, side)
        at = request.at_close
        if evaluation_id is not None:
            identifier(evaluation_id)
        content = (side, request.at_close, evaluation_id)
        if signal_id in self._signals:
            if self._signals[signal_id][0] != content:
                raise ValidationError('ID de sinal conflitante')
            return self._signals[signal_id][1]
        self._active()
        self._phase_close(request)
        self._emit(at, 'SIGNAL', signal_id=signal_id, evaluation_id=evaluation_id, side=side)
        order = self._submit(request)
        decision = dict(signal_id=signal_id, evaluation_id=evaluation_id,
                        decision_id=f'{signal_id}:decision', approved=order.status == 'NEW',
                        reason=order.reason, order_id=order.request.id,
                        intent_id=f'{signal_id}:intent' if order.status == 'NEW' else None)
        self._emit(at, 'DECISION', **decision)
        if order.status == 'NEW':
            self._emit(at, 'INTENTION', **decision)
        self._signals[signal_id] = (content, decision)
        return decision

    @atomic
    def on_open(self, opening):
        self._active()
        if not isinstance(opening, Opening):
            raise ValidationError('Abertura exige Opening sem OHLCV futuro')
        self._validate_market_event(opening)
        if opening.at in self._seen_opens:
            if self._seen_opens[opening.at] != opening:
                raise ValidationError('Abertura conflitante')
            return
        if self._opening is not None:
            if self._closed is None or self._opening.at != self._closed.open_time:
                raise ValidationError('Fechar candle antes de nova abertura')
            if opening.at != self._closed.close_time:
                if self.config.mode != 'MANUAL' and opening.at > self._closed.close_time:
                    self.status = 'INTERRUPTED'
                    self.diagnostic = dict(reason='DATA_GAP', expected=self._closed.close_time, found=opening.at)
                    self._emit(self._closed.close_time, 'INTERRUPTED', **self.diagnostic)
                    return
                raise ValidationError('Abertura fora de ordem ou lacuna')
        else:
            self._ledger = self._ledger.start(opening.at)
            self._observe(opening.at, 'INITIAL')
        self._opening = opening
        self._mark, self._mark_at = opening.price, opening.at
        self._emit(opening.at, 'OPEN', source=opening.source, symbol=opening.symbol,
                   interval=opening.interval, price=opening.price)
        self._observe(opening.at, 'OPEN')
        self._seen_opens[opening.at] = opening
        trigger = opening_trigger(self._group, opening)
        if trigger:
            self._protect(trigger, opening.at)
        elif self.pending is not None:
            order = self._orders[self.pending]
            if order.request.side == 'BUY':
                own = self._cash_reservation(order.request.id).quantity
                reason, details = revalidate(self.config, self.snapshot(opening.at, own_reserve=own), order.sizing)
                self._emit(opening.at, 'RISK_REVALIDATION', order_id=order.request.id, reason=reason, details=details)
                self._record('REVALIDATION', opening.at, len(self._events), dict(order_id=order.request.id, reason=reason, details=details))
                if reason:
                    self._cancel_order(order.request.id, opening.at, 'REJECTED', reason)
                    return
            details = dict(exit_origin='SIGNAL' if self.config.mode != 'MANUAL' else 'MANUAL',
                           execution_time_model='OPEN_EVENT', intrabar_time_known=True,
                           interval_start=opening.at, interval_end=opening.at, ambiguous=False)
            self._execute(order.request.id, opening.price, opening.at, details)

    @atomic
    def on_close(self, candle):
        self._active()
        if not isinstance(candle, Candle):
            raise ValidationError('Fechamento exige Candle')
        self._validate_market_event(candle)
        if candle.key in self._seen_candles:
            if self._seen_candles[candle.key] != candle:
                raise ValidationError('Candle conflitante')
            return
        if self._opening != candle.opening():
            raise ValidationError('Fechamento sem abertura correspondente')
        self._emit(candle.close_time, 'BAR_RANGE', candle=candle)
        trigger = range_trigger(self._group, candle)
        if trigger:
            self._protect(trigger, candle.close_time)
        self._closed = candle
        self._mark, self._mark_at = candle.close, candle.close_time
        self._emit(candle.close_time, 'CLOSE', candle=candle)
        self._observe(candle.close_time, 'CLOSE')
        self._seen_candles[candle.key] = candle
        if self.strategy is not None:
            evaluation = self.strategy.on_close(candle)
            eid = f'evaluation:{candle.close_time.isoformat()}'
            self._emit(candle.close_time, 'EVALUATION', evaluation_id=eid, **evaluation)
            if evaluation['side']:
                self.handle_signal(f'{eid}:signal', evaluation['side'], candle.close_time, eid)

    def _protect(self, details, at):
        self._mark, self._mark_at = details['reference_price'], at
        self._emit(at, 'PROTECTION_TRIGGER', protection_id=self._group.id, **details)
        self._observe(at, 'PROTECTION_TRIGGER')
        self._record('PROTECTION_TRIGGER', at, len(self._events), dict(protection_id=self._group.id, **details))
        if self.pending is not None:
            self._cancel_order(self.pending, at, 'CANCELED', 'PROTECTIVE_EXIT_PREEMPTED')
        oid = f"{self._group.id}:{details['exit_origin']}"
        request = RiskRequest(oid, at, 'SELL')
        self._orders[oid] = RiskOrder(request, 'NEW', len(self._events), quantity=self.balance.asset_quantity)
        self._pending = oid
        self._emit(at, 'ACCEPTED', order_id=oid, status='NEW', reason=details['exit_origin'])
        self._adjust('TRANSFER', at, [replace(self._asset_reservation(), owner_id=oid)])
        self._execute(oid, details['reference_price'], at, details)

    def _execute(self, order_id, reference, at, details):
        order = self._orders[order_id]
        price = effective_price(reference, order.request.side, self.config.slippage_rate)
        fill = Fill(f'{order_id}:fill:1', order_id, order.request.side, order.quantity,
                    price, order.quantity*price*self.config.fee_rate, at)
        self._eligible = (fill, reference, details)
        self.apply_fill(fill)
        self._eligible = None

    @atomic
    def apply_fill(self, fill):
        if not isinstance(fill, Fill):
            raise ValidationError('Preenchimento exige Fill')
        if fill.id in self._fills:
            if self._fills[fill.id] != fill:
                raise ValidationError('ID de execução conflitante')
            return self._fills[fill.id]
        self._active()
        if self._eligible is None or self._eligible[0] != fill:
            raise ValidationError('Execução sem evento elegível')
        _, reference, details = self._eligible
        order = self._orders.get(fill.order_id)
        if order is None or order.status != 'NEW' or self.pending != fill.order_id:
            raise ValidationError('Execução sem ordem pendente')
        before = self.balance
        if fill.side == 'BUY':
            sizing = order.sizing
            group = Protection(f'{fill.id}:protection', f'{fill.id}:lot', fill.quantity,
                               sizing['stop'], sizing['target'], sizing['budget'], fill.at,
                               self._opening.at+timedelta(minutes=1))
            operations = (replace(self._cash_reservation(fill.order_id), status='CONSUMED'),
                          Reservation(f'{group.id}:asset', group.id, getattr(self.config, 'base_asset', 'BTC'), fill.quantity))
        else:
            group = replace(self._group, status='CLOSED', exit_details=dict(
                **details, effective_price=fill.price, at=fill.at, order_id=fill.order_id,
                budget=self._group.budget, stop=self._group.stop, target=self._group.target))
            operations = (replace(self._asset_reservation(), status='CONSUMED'),)
        seq = len(self._events)+1
        prepared = self._ledger.prepare(fill, reference, seq, operations)
        prepared.reconcile()
        self._ledger = prepared
        self._fills[fill.id] = fill
        self._orders[fill.order_id] = replace(order, status='FILLED')
        self._pending = None
        if fill.side == 'BUY':
            self._group = group
        else:
            group = replace(group, exit_details={**group.exit_details, 'realized_pnl': prepared.trades[-1].net_pnl})
            self._groups, self._group = (*self._groups, group), None
            self._last_exit_candle = self._opening.at
        self._emit(fill.at, 'FILLED', order_id=fill.order_id, execution_id=fill.id,
                   fill=fill, gross=fill.price*fill.quantity, before=before, after=self.balance,
                   reference_price=reference, effective_price=fill.price,
                   fee_rate=self.config.fee_rate, slippage_rate=self.config.slippage_rate, **{k:v for k,v in details.items() if k != 'reference_price'})
        self._observe(fill.at, 'FILL')
        return fill

    @atomic
    def finish(self):
        if self.finished:
            return
        self._active()
        if self._closed is None:
            if self.config.schema_version == 6 and self._opening is None:
                self._finished, self.status = True, 'UNAVAILABLE'
                return
            raise ValidationError('Encerrar exige último fechamento')
        if self._opening.at != self._closed.open_time:
            raise ValidationError('Encerrar exige último fechamento')
        at = self._closed.close_time
        if self.pending:
            reason = 'NO_FUTURE_OPEN'
            if self.config.schema_version == 6 and self.config.instrument.available_until == at:
                reason = 'INSTRUMENT_UNAVAILABLE'
            self._cancel_order(self.pending, at, 'UNEXECUTED', reason)
        if self._group:
            self._adjust('RELEASE', at, [replace(self._asset_reservation(), status='RELEASED')])
            self._groups = (*self._groups, replace(self._group, status='ENDED_WITH_OPEN_POSITION'))
            self._group = None
        self._ledger.reconcile()
        self._finished, self.status = True, 'COMPLETED'
        self._emit(at, 'END', balance=self.balance)


def replay_risk(candles, config, run_id='api', diagnostics=()):
    validated, duplicates = validate_series(candles, contiguous=config.mode == 'MANUAL')
    if config.mode == 'MANUAL':
        closes = {c.close_time for c in validated}
        if any(r.at_close not in closes for r in config.orders):
            raise ValidationError('Ação deve referenciar fechamento existente')
    from .coverage import matching, eligible
    matching(validated, config)
    source_candles = validated
    if config.schema_version == 6:
        validated = tuple(c for c in validated if eligible(c, config))
    session = RiskSession(config, run_id)
    session._source_candles = source_candles
    session._input_diagnostics = (*diagnostics, *duplicates)
    if not validated:
        session.finish()
        return session
    schedule, by_close = defaultdict(list), defaultdict(list)
    for request in config.orders:
        schedule[request.at_close].append(request)
    for record in (*diagnostics, *duplicates):
        item = dict(record)
        at = item.pop('at', validated[0].close_time)
        by_close[at].append(item)
    for candle in validated:
        session.on_open(candle.opening())
        if session.status == 'INTERRUPTED':
            return session
        session.on_close(candle)
        for request in schedule[candle.close_time]:
            session.submit(request)
        for diagnostic in by_close[candle.close_time]:
            session._emit(candle.close_time, 'DIAGNOSTIC', **diagnostic)
    session.finish()
    return session
