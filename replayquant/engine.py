"""Replay sequencial: fechamento, submissão manual, abertura, preenchimento."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from .data import validate_schedule, validate_series
from .execution import amounts, make_fill, effective_price, make_sma_fill
from .models import Candle, Config, Fill, Opening, Order, Request, SMAConfig
from .portfolio import after_fill
from .ledger import Ledger
from .strategies import SMACross
from .validation import ValidationError, financial, identifier


class Session:
    """Estado local; consultas retornam snapshots, mutações passam pelos eventos."""

    def __init__(self, config: Config, run_id: str):
        if not isinstance(config, (Config, SMAConfig)):
            raise ValidationError("Esperado Config")
        self.config = config
        self.run_id = identifier(run_id, "run_id")
        self._ledger = Ledger.initial(config.initial_cash, run_id)
        self._orders = {}
        self._fills = {}
        self._events = []
        self._pending = None
        self._opening = None
        self._closed = None
        self._finished = False

    @property
    def balance(self):
        return self._ledger.balance

    @property
    def fees(self):
        return self._ledger.fees

    @property
    def ledger(self):
        return self._ledger

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
        self._events.append({"schema_version": 2 if isinstance(self.config, SMAConfig) else 1, "run_id": self.run_id,
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
        if self._ledger.entries[0].at is None:
            self._ledger = self._ledger.start(opening.at)
        self._opening = opening
        self._emit(opening.at, "OPEN", source=opening.source, symbol=opening.symbol,
                   interval=opening.interval, price=opening.price)
        if self._pending is not None:
            self.apply_fill(self._make_fill(self._orders[self._pending].request, opening))

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
            if self.balance.cash < self._estimate_buy(self._closed.close):
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
        expected = self._make_fill(order.request, self._opening)
        if fill != expected or len(self._events) <= order.submitted_seq:
            raise ValidationError("Execução incompatível com ordem, preço ou evento elegível")
        reason = None
        gross, fee = fill.price * fill.quantity, fill.fee
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
        prepared = self._ledger.prepare(fill, self._opening.price, len(self._events) + 1, after)
        # Commit de todos os efeitos somente após os cálculos e verificações.
        self._ledger = prepared
        self._fills[fill.id] = fill
        self._orders[order.request.id] = replace(order, status="FILLED")
        self._pending = None
        self._emit(fill.at, "FILLED", order_id=fill.order_id, execution_id=fill.id,
                   fill=fill, gross=gross, before=before, after=after)
        return fill

    def _make_fill(self, request, opening):
        return make_fill(request, opening, self.config.quantity, self.config.fee_rate)

    def _estimate_buy(self, reference):
        return _add(*amounts(reference, self.config.quantity, self.config.fee_rate))

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
    if isinstance(config, SMAConfig):
        return replay_sma(candles, config, run_id, diagnostics)
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


class SMASession(Session):
    """API progressiva: on_open(Opening), on_close(Candle), finish()."""

    def __init__(self, config, run_id="api"):
        if not isinstance(config, SMAConfig):
            raise ValidationError("SMASession exige SMAConfig")
        super().__init__(config, run_id)
        self.strategy = SMACross(config.strategy)
        self.status = "RUNNING"
        self.diagnostic = None
        self._seen_candles = {}
        self._seen_opens = {}
        self._signals = {}
        self._decisions = {}

    def _active(self):
        if self.status == "INTERRUPTED":
            raise ValidationError("Sessão interrompida; iniciar nova execução")
        super()._active()

    def _interrupt(self, reason, **details):
        self.status = "INTERRUPTED"
        self.diagnostic = {"reason": reason, **details}
        at = self._closed.close_time if self._closed else None
        self._emit(at, "INTERRUPTED", **self.diagnostic)

    def on_open(self, opening):
        self._active()
        if not isinstance(opening, Opening):
            raise ValidationError("Abertura exige Opening sem OHLCV futuro")
        if opening.at in self._seen_opens:
            if self._seen_opens[opening.at] == opening:
                return
            self._interrupt("CONFLICTING_OPEN", found=opening.at)
            raise ValidationError("Abertura conflitante")
        if self._closed is not None and opening.at > self._closed.close_time:
            if self._opening.at != self._closed.open_time:
                raise ValidationError("Fechar candle anterior antes de abrir outro")
            self._interrupt("DATA_GAP", expected=self._closed.close_time, found=opening.at,
                            last_accepted_seq=len(self._events))
            return
        try:
            super().on_open(opening)
        except Exception:
            self._interrupt("INVALID_OPEN_OR_ARITHMETIC")
            raise
        self._seen_opens[opening.at] = opening

    def on_close(self, candle):
        self._active()
        if not isinstance(candle, Candle):
            raise ValidationError("Fechamento exige Candle")
        if candle.key in self._seen_candles:
            if self._seen_candles[candle.key] == candle:
                return
            self._interrupt("CONFLICTING_CANDLE", found=candle.close_time)
            raise ValidationError("Candle conflitante")
        if self._opening != candle.opening():
            raise ValidationError("Fechamento sem abertura correspondente")
        # Prepare o indicador e cálculos de decisão antes de aceitar o fechamento.
        try:
            candidate = deepcopy(self.strategy)
            evaluation = candidate.on_close(candle)
            if evaluation["side"] == "BUY" and self._pending is None and self.balance.btc == 0:
                self._estimate_buy(candle.close)
        except Exception:
            self._interrupt("INDICATOR_OR_ARITHMETIC_FAILURE")
            raise
        super().on_close(candle)
        self.strategy = candidate
        self._seen_candles[candle.key] = candle
        eid = f"evaluation:{candle.close_time.isoformat()}"
        self._emit(candle.close_time, "EVALUATION", evaluation_id=eid, **evaluation)
        if evaluation["side"]:
            self.handle_signal(f"{eid}:signal", evaluation["side"], candle.close_time, eid)

    @financial
    def _estimate_buy(self, reference):
        price = effective_price(reference, "BUY", self.config.slippage_rate)
        gross = price * self.config.quantity
        return gross + gross * self.config.fee_rate

    def _make_fill(self, request, opening):
        return make_sma_fill(request, opening, self.config.quantity,
                             self.config.fee_rate, self.config.slippage_rate)

    def handle_signal(self, signal_id, side, at, evaluation_id=None):
        """Integração incremental de sinal identificado; duplicata é inócua."""
        request = Request(f"{identifier(signal_id)}:order", at, side)
        at = request.at_close
        if evaluation_id is not None:
            identifier(evaluation_id, "evaluation_id")
        content = (side, at, evaluation_id)
        if signal_id in self._signals:
            if self._signals[signal_id] != content:
                raise ValidationError("ID de sinal conflitante")
            return deepcopy(self._decisions[signal_id])
        self._active()
        if (self._closed is None or request.at_close != self._closed.close_time
                or self._opening.at != self._closed.open_time):
            raise ValidationError("Sinal exige fase de fechamento")
        reason = None
        if self.pending is not None:
            reason = "ORDER_PENDING"
        elif side == "BUY" and self.balance.btc != 0:
            reason = "POSITION_OPEN"
        elif side == "SELL" and self.balance.btc < self.config.quantity:
            reason = "INSUFFICIENT_ASSET"
        elif side == "BUY" and self.balance.cash < self._estimate_buy(self._closed.close):
            reason = "INSUFFICIENT_CASH"
        intent_id = f"{signal_id}:intent" if reason is None else None
        decision = {"signal_id": signal_id, "evaluation_id": evaluation_id,
                    "decision_id": f"{signal_id}:decision", "approved": reason is None,
                    "reason": reason, "intent_id": intent_id,
                    "order_id": request.id if reason is None else None}
        self._signals[signal_id] = content
        self._decisions[signal_id] = decision
        self._emit(at, "SIGNAL", signal_id=signal_id, evaluation_id=evaluation_id, side=side)
        self._emit(at, "DECISION", **decision)
        if reason is None:
            self._emit(at, "INTENTION", **decision)
            super().submit(request)
        return deepcopy(decision)

    def submit(self, request):
        # Ordens externas não podem contornar a origem SMA; repetições aceitas podem ser consultadas.
        if isinstance(request, Request) and request.id in self._orders:
            return super().submit(request)
        raise ValidationError("Modo SMA exige handle_signal; não aceita roteiro manual")

    @financial
    def apply_fill(self, fill):
        before = len(self._events)
        result = super().apply_fill(fill)
        if result is not None and len(self._events) > before:
            self._events[-1].update(reference_price=self._opening.price,
                                     effective_price=fill.price,
                                     fee_rate=self.config.fee_rate,
                                     slippage_rate=self.config.slippage_rate)
        return result

    def finish(self):
        if not self.finished:
            self._active()
        super().finish()
        self.status = "COMPLETED"


def replay_sma(candles, config, run_id="api", diagnostics=()):
    validated, duplicates = validate_series(candles, contiguous=False)
    session = SMASession(config, run_id)
    by_close = defaultdict(list)
    for diagnostic in (*diagnostics, *duplicates):
        payload = dict(diagnostic)
        at = payload.pop("at", validated[-1].close_time)
        by_close[at].append(payload)
    for candle in validated:
        session.on_open(candle.opening())
        if session.status == "INTERRUPTED":
            return session
        session.on_close(candle)
        for diagnostic in by_close[candle.close_time]:
            session._emit(candle.close_time, "DIAGNOSTIC", **diagnostic)
    session.finish()
    return session
