"""Extensão imutável do ledger existente com contas disponíveis e reservadas."""
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from .ledger import Entry, Ledger
from .metrics import integer
from .validation import ValidationError, decimal_value, financial, identifier, utc

ZERO = Decimal('0')


@dataclass(frozen=True)
class Reservation:
    id: str
    owner_id: str
    currency: str
    quantity: Decimal
    status: str = 'HELD'

    def __post_init__(self):
        identifier(self.id)
        identifier(self.owner_id, 'owner_id')
        if self.currency not in ('USDT', 'BTC') or self.status not in ('HELD', 'CONSUMED', 'RELEASED'):
            raise ValidationError('Moeda/estado de reserva inválido')
        decimal_value(self.quantity, 'reservation.quantity', positive=True, bounded=False)


@dataclass(frozen=True)
class ReserveEntry(Entry):
    reservation_id: str | None = None
    reservation_owner_id: str | None = None
    cash_available_delta: Decimal = ZERO
    cash_reserved_delta: Decimal = ZERO
    asset_available_delta: Decimal = ZERO
    asset_reserved_delta: Decimal = ZERO
    cash_available_after: Decimal = ZERO
    cash_reserved_after: Decimal = ZERO
    asset_available_after: Decimal = ZERO
    asset_reserved_after: Decimal = ZERO
    reservation_operations: tuple[Reservation, ...] = ()

    def __post_init__(self):
        if self.entry_type in ('INITIAL_BALANCE', 'FILL'):
            super().__post_init__()
        else:
            if self.schema_version != 4 or self.entry_type not in ('RESERVE', 'RELEASE', 'TRANSFER'):
                raise ValidationError('Entrada de reserva inválida')
            identifier(self.run_id)
            identifier(self.ledger_id)
            integer(self.ledger_seq, 'ledger_seq', 2)
            integer(self.source_event_seq, 'source_event_seq', 1)
            object.__setattr__(self, 'at', utc(self.at))
            if any(getattr(self, k) != 0 for k in ('cash_delta', 'asset_delta', 'gross', 'fee')):
                raise ValidationError('Reserva não pode alterar total/taxa')
        for name in ('cash_available_after', 'cash_reserved_after', 'asset_available_after', 'asset_reserved_after'):
            decimal_value(getattr(self, name), name, bounded=False)
        for name in ('cash_available_delta', 'cash_reserved_delta', 'asset_available_delta', 'asset_reserved_delta'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValidationError('Delta de reserva inválido')
        if type(self.reservation_operations) is not tuple or not all(isinstance(r, Reservation) for r in self.reservation_operations):
            raise ValidationError('Operações de reserva inválidas')


@dataclass(frozen=True)
class ReservationLedger:
    funds: Ledger
    entries: tuple[ReserveEntry, ...]
    reservations: tuple[Reservation, ...] = ()
    history: tuple[dict, ...] = ()

    @classmethod
    def initial(cls, capital, run_id, at=None):
        funds = Ledger.initial(capital, run_id, at=at)
        row = ReserveEntry(**{**asdict(funds.entries[0]), 'schema_version': 4},
                           cash_available_delta=capital, cash_available_after=capital)
        return cls(funds, (row,))

    def start(self, at):
        funds = self.funds.start(at)
        return replace(self, funds=funds, entries=(replace(self.entries[0], at=funds.entries[0].at), *self.entries[1:]))

    @property
    def balance(self):
        return self.funds.balance

    @property
    def fees(self):
        return self.funds.fees

    @property
    def cost_basis(self):
        return self.funds.cost_basis

    @property
    def trades(self):
        return self.funds.trades

    @property
    def realized(self):
        return self.funds.realized

    @property
    def slippage(self):
        return self.funds.slippage

    @property
    def open_fill(self):
        return self.funds.open_fill

    def held(self, reservation_id):
        item = next((r for r in self.reservations if r.id == reservation_id), None)
        if item is None or item.status != 'HELD':
            raise ValidationError('Reserva não está retida')
        return item

    @financial
    def _append(self, funds, values, operations):
        if type(operations) is not tuple or not all(isinstance(r, Reservation) for r in operations):
            raise ValidationError('Operações exigem tuple de Reservation')
        previous = self.entries[-1]
        at, seq = values['at'], values['source_event_seq']
        if at < previous.at or seq <= previous.source_event_seq:
            raise ValidationError('Reserva/movimento fora de ordem')
        states = {r.id: r for r in self.reservations}
        history = list(self.history)
        for index, operation in enumerate(operations):
            old = states.get(operation.id)
            if old is None:
                if operation.status != 'HELD':
                    raise ValidationError('Reserva deve começar retida')
            elif (old.status != 'HELD' or (old.currency, old.quantity) != (operation.currency, operation.quantity)
                  or old == operation):
                raise ValidationError('Transição de reserva inválida')
            states[operation.id] = operation
            history.append(dict(schema_version=4, run_id=values['run_id'],
                                record_id=f"{values['ledger_id']}:reservation:{index}",
                                ledger_id=values['ledger_id'], source_event_seq=seq, at=at,
                                reservation_id=operation.id, owner_id=operation.owner_id,
                                from_owner_id=old.owner_id if old else None, currency=operation.currency,
                                quantity=operation.quantity, status=operation.status,
                                record_type=values['entry_type']))
        cash_reserved = sum((r.quantity for r in states.values() if r.status == 'HELD' and r.currency == 'USDT'), ZERO)
        asset_reserved = sum((r.quantity for r in states.values() if r.status == 'HELD' and r.currency == 'BTC'), ZERO)
        cash_available = funds.balance.cash - cash_reserved
        asset_available = funds.balance.btc - asset_reserved
        if cash_available < 0 or asset_available < 0:
            raise ValidationError('Reserva excede saldo total')
        first = operations[0] if operations else None
        row = ReserveEntry(**values, reservation_id=first.id if first else None,
                           reservation_owner_id=first.owner_id if first else None,
                           cash_available_delta=cash_available-previous.cash_available_after,
                           cash_reserved_delta=cash_reserved-previous.cash_reserved_after,
                           asset_available_delta=asset_available-previous.asset_available_after,
                           asset_reserved_delta=asset_reserved-previous.asset_reserved_after,
                           cash_available_after=cash_available, cash_reserved_after=cash_reserved,
                           asset_available_after=asset_available, asset_reserved_after=asset_reserved,
                           reservation_operations=operations)
        return ReservationLedger(funds, (*self.entries, row), tuple(states.values()), tuple(history))

    @financial
    def adjust(self, kind, operation_id, at, seq, operations):
        if kind not in ('RESERVE', 'RELEASE', 'TRANSFER'):
            raise ValidationError('Tipo de ajuste inválido')
        identifier(operation_id)
        at = utc(at)
        integer(seq, 'seq', 1)
        if type(operations) is not tuple or not operations or not all(isinstance(r, Reservation) for r in operations):
            raise ValidationError('Ajuste exige operações de reserva')
        ledger_id = f'STRATEGY:{operation_id}'
        for row in self.entries:
            if row.ledger_id == ledger_id:
                if (row.entry_type, row.at, row.reservation_operations) != (kind, at, operations):
                    raise ValidationError('ID de ajuste conflitante')
                return self
        row = self.funds.entries[-1]
        values = dict(schema_version=4, run_id=row.run_id, portfolio=row.portfolio,
                      ledger_id=ledger_id, ledger_seq=len(self.entries)+1, at=at, source_event_seq=seq,
                      entry_type=kind, order_id=None, execution_id=None, lot_id=None, side=None,
                      quantity=None, reference_price=None, effective_price=None, cash_delta=ZERO,
                      asset_delta=ZERO, gross=ZERO, fee=ZERO, cash_after=row.cash_after,
                      asset_after=row.asset_after, fees_after=row.fees_after, cost_basis_after=row.cost_basis_after)
        return self._append(self.funds, values, operations)

    @financial
    def prepare(self, fill, reference_price, source_event_seq, operations=()):
        funds = self.funds.prepare(fill, reference_price, source_event_seq)
        if funds is self.funds:
            return self
        values = asdict(funds.entries[-1])
        values.update(schema_version=4, ledger_seq=len(self.entries)+1)
        return self._append(funds, values, operations)

    @financial
    def reconcile(self):
        result = self.funds.reconcile()
        ca = cr = aa = ar = cash = asset = ZERO
        states, ids, histories, fill_ids = {}, set(), [], set()
        source, at = -1, None
        for index, row in enumerate(self.entries, 1):
            if (row.ledger_seq != index or row.source_event_seq <= source or row.at is None
                    or (at is not None and row.at < at) or row.ledger_id in ids
                    or (row.run_id, row.portfolio) != (self.entries[0].run_id, 'STRATEGY')):
                raise ValidationError('RECONCILIATION_FAILED: sequência da reserva')
            ids.add(row.ledger_id)
            ca += row.cash_available_delta
            cr += row.cash_reserved_delta
            aa += row.asset_available_delta
            ar += row.asset_reserved_delta
            cash += row.cash_delta
            asset += row.asset_delta
            if (ca, cr, aa, ar, cash, asset) != (row.cash_available_after, row.cash_reserved_after,
                    row.asset_available_after, row.asset_reserved_after, row.cash_after, row.asset_after):
                raise ValidationError('RECONCILIATION_FAILED: deltas das contas')
            if min(ca, cr, aa, ar) < 0 or ca+cr != cash or aa+ar != asset:
                raise ValidationError('RECONCILIATION_FAILED: disponível + reservado != total')
            for operation in row.reservation_operations:
                previous = states.get(operation.id)
                if previous is None and operation.status != 'HELD':
                    raise ValidationError('RECONCILIATION_FAILED: reserva sem origem')
                if previous is not None and (previous.status != 'HELD' or
                        (previous.quantity, previous.currency) != (operation.quantity, operation.currency)):
                    raise ValidationError('RECONCILIATION_FAILED: transição da reserva')
                histories.append(dict(schema_version=4, run_id=row.run_id,
                                      record_id=f'{row.ledger_id}:reservation:{len([h for h in histories if h["ledger_id"] == row.ledger_id])}',
                                      ledger_id=row.ledger_id, source_event_seq=row.source_event_seq, at=row.at,
                                      reservation_id=operation.id, owner_id=operation.owner_id,
                                      from_owner_id=previous.owner_id if previous else None,
                                      currency=operation.currency, quantity=operation.quantity,
                                      status=operation.status, record_type=row.entry_type))
                states[operation.id] = operation
            held_cash = sum((r.quantity for r in states.values() if r.currency == 'USDT' and r.status == 'HELD'), ZERO)
            held_asset = sum((r.quantity for r in states.values() if r.currency == 'BTC' and r.status == 'HELD'), ZERO)
            if (held_cash, held_asset) != (cr, ar):
                raise ValidationError('RECONCILIATION_FAILED: titularidade da reserva')
            if row.entry_type == 'FILL':
                original = next((r for r in self.funds.entries if r.execution_id == row.execution_id), None)
                if row.execution_id in fill_ids or original is None or any(getattr(original, k) != getattr(row, k) for k in Entry.__dataclass_fields__ if k not in ('schema_version','ledger_seq')):
                    raise ValidationError('RECONCILIATION_FAILED: fill financeiro')
                fill_ids.add(row.execution_id)
            elif index > 1 and (row.entry_type not in ('RESERVE','RELEASE','TRANSFER') or any(getattr(row,k) != 0 for k in ('cash_delta','asset_delta','gross','fee'))):
                raise ValidationError('RECONCILIATION_FAILED: movimento não financeiro')
            source, at = row.source_event_seq, row.at
        if tuple(states.values()) != self.reservations or tuple(histories) != self.history or fill_ids != {e.execution_id for e in self.funds.entries if e.entry_type == 'FILL'}:
            raise ValidationError('RECONCILIATION_FAILED: histórico final das reservas')
        if (cash, asset) != (self.balance.cash, self.balance.btc):
            raise ValidationError('RECONCILIATION_FAILED: ledger financeiro e contas')
        result.update(cash_available=ca, cash_reserved=cr, asset_available=aa,
                      asset_reserved=ar, reservation_entries_checked=len(self.entries))
        return result
