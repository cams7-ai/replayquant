"""Replay sequencial: fechamento, submissão manual, abertura, preenchimento."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from .data import validate_schedule, validate_series
from .execution import amounts, make_fill
from .models import Candle, Config, Fill, Opening, Order, Request
from .portfolio import Balance, after_fill
from .validation import ValidationError, financial, identifier


class Session:
    """Estado local; consultas retornam snapshots, mutações passam pelos eventos."""

    def __init__(self, config: Config, run_id: str):
        if not isinstance(config, Config):
            raise ValidationError("Esperado Config")
        self.config = config
        self.run_id = identifier(run_id, "run_id")
        self._balance = Balance(config.initial_cash)
        self._fees = Decimal("0")
        self._orders = {}
        self._fills = {}
        self._events = []
        self._pending = None
        self._opening = None
        self._closed = None
        self._finished = False

    @property
    def balance(self):
        return self._balance

    @property
    def fees(self):
        return self._fees

    @property
    def orders(self):
        return tuple(self._orders.values())

    @property
    def fills(self):
        return tuple(self._fills.values())

    @property
    def events(self):
        return deepcopy(self._events)

    @property
    def pending(self):
        return self._pending

    @property
    def finished(self):
        return self._finished

    def _emit(self, at, event_type, **payload):
        self._events.append({"schema_version": 1, "run_id": self.run_id,
                             "seq": len(self._events) + 1, "at": at,
                             "type": event_type, **payload})

    def _active(self):
        if self._finished:
            raise ValidationError("Sessão já encerrada")

    def on_open(self, opening: Opening):
        self._active()
        if not isinstance(opening, Opening):
            raise ValidationError("Abertura exige Opening sem OHLCV futuro")
        if self._opening is not None:
            if self._closed is None or self._closed.open_time != self._opening.at:
                raise ValidationError("Fechar candle anterior antes de abrir outro")
            if opening.at != self._closed.close_time:
                raise ValidationError("Abertura fora de ordem ou com lacuna")
        self._opening = opening
        self._emit(opening.at, "OPEN", source=opening.source, symbol=opening.symbol,
                   interval=opening.interval, price=opening.price)
        if self._pending is not None:
            self.apply_fill(make_fill(self._orders[self._pending].request, opening,
                                      self.config.quantity, self.config.fee_rate))

    def on_close(self, candle: Candle):
        self._active()
        if not isinstance(candle, Candle) or self._opening != candle.opening():
            raise ValidationError("Fechamento sem abertura correspondente")
        if self._closed is not None and candle.close_time <= self._closed.close_time:
            raise ValidationError("Fechamento repetido ou fora de ordem")
        self._closed = candle
        self._emit(candle.close_time, "CLOSE", candle=candle)

    def submit(self, request: Request):
        if not isinstance(request, Request):
            raise ValidationError("Submissão exige Request")
        if request.id in self._orders:
            existing = self._orders[request.id]
            if existing.request != request:
                raise ValidationError("ID de ordem conflitante")
            return existing
        self._active()
        if (self._closed is None or request.at_close != self._closed.close_time
                or self._opening.at != self._closed.open_time):
            raise ValidationError("Submissão exige a fase do fechamento indicado")
        # Aritmética potencialmente falha ocorre antes de registrar/alterar a ordem.
        reason = None
        if self._pending is not None:
            reason = "ORDER_PENDING"
        elif request.side == "BUY" and self.balance.btc != 0:
            reason = "POSITION_OPEN"
        elif request.side == "SELL" and self.balance.btc < self.config.quantity:
            reason = "INSUFFICIENT_ASSET"
        elif request.side == "BUY":
            gross, fee = amounts(self._closed.close, self.config.quantity, self.config.fee_rate)
            if self.balance.cash < _add(gross, fee):
                reason = "INSUFFICIENT_CASH"
        self._emit(request.at_close, "SUBMITTED", order_id=request.id,
                   side=request.side, quantity=self.config.quantity)
        order = Order(request, "REJECTED" if reason else "NEW", len(self._events), reason)
        self._orders[request.id] = order
        if reason is None:
            self._pending = request.id
        self._emit(request.at_close, "REJECTED" if reason else "ACCEPTED", order_id=request.id,
                   status=order.status, reason=reason)
        return order

    @financial
    def apply_fill(self, fill: Fill):
        if not isinstance(fill, Fill):
            raise ValidationError("Esperado Fill")
        if fill.id in self._fills:
            if self._fills[fill.id] != fill:
                raise ValidationError("ID de execução conflitante")
            return self._fills[fill.id]
        self._active()
        order = self._orders.get(fill.order_id)
        if (order is None or order.status != "NEW" or self._pending != fill.order_id
                or self._opening is None or self._closed is None
                or self._opening.at != self._closed.close_time):
            raise ValidationError("Execução sem ordem pendente na fase de abertura")
        expected = make_fill(order.request, self._opening, self.config.quantity, self.config.fee_rate)
        if fill != expected or len(self._events) <= order.submitted_seq:
            raise ValidationError("Execução incompatível com ordem, preço ou evento elegível")
        reason = None
        gross, fee = amounts(fill.price, fill.quantity, self.config.fee_rate)
        if fill.side == "BUY" and self.balance.cash < gross + fee:
            reason = "INSUFFICIENT_CASH"
        elif fill.side == "SELL" and self.balance.btc < fill.quantity:
            reason = "INSUFFICIENT_ASSET"
        if reason:
            self._orders[order.request.id] = replace(order, status="REJECTED", reason=reason)
            self._pending = None
            self._emit(fill.at, "REJECTED", order_id=fill.order_id, status="REJECTED", reason=reason)
            return None
        before = self.balance
        after = after_fill(before, fill)
        total_fees = self._fees + fill.fee
        # Commit de todos os efeitos somente após os cálculos e verificações.
        self._balance = after
        self._fees = total_fees
        self._fills[fill.id] = fill
        self._orders[order.request.id] = replace(order, status="FILLED")
        self._pending = None
        self._emit(fill.at, "FILLED", order_id=fill.order_id, execution_id=fill.id,
                   fill=fill, gross=gross, before=before, after=after)
        return fill

    def finish(self):
        if self._finished:
            return
        if self._closed is None or self._opening.at != self._closed.open_time:
            raise ValidationError("Encerrar exige o último fechamento")
        if self._pending is not None:
            order = self._orders[self._pending]
            self._orders[self._pending] = replace(order, status="UNEXECUTED", reason="NO_FUTURE_OPEN")
            self._emit(self._closed.close_time, "UNEXECUTED", order_id=self._pending,
                       status="UNEXECUTED", reason="NO_FUTURE_OPEN")
            self._pending = None
        self._finished = True
        self._emit(self._closed.close_time, "END", balance=self.balance)


@financial
def _add(a, b):
    return a + b


def replay(candles, config, run_id="api", diagnostics=()):
    validated, duplicate_diagnostics = validate_series(candles)
    validate_schedule(validated, config)
    session = Session(config, run_id)
    for diagnostic in (*diagnostics, *duplicate_diagnostics):
        session._emit(validated[0].open_time, "DIAGNOSTIC", **diagnostic)
    schedule = defaultdict(list)
    for request in config.orders:
        schedule[request.at_close].append(request)
    for candle in validated:
        session.on_open(candle.opening())
        session.on_close(candle)
        for request in schedule[candle.close_time]:
            session.submit(request)
    session.finish()
    return session
