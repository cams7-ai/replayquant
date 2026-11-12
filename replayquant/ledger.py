"""Ledger imutável; preparar uma transação não modifica a carteira aceita."""
from dataclasses import dataclass, replace, asdict
from decimal import Decimal
from .models import Fill, side_value
from .portfolio import Balance, AssetBalance, after_fill
from .validation import ValidationError, decimal_value, identifier, utc, financial
from .metrics import integer, seconds, percentage

ZERO = Decimal('0')
PORTFOLIOS = ('STRATEGY', 'HOLD_USDT', 'BUY_HOLD_BTC', 'BUY_HOLD_ASSET')


@dataclass(frozen=True)
class Entry:
    schema_version: int
    run_id: str
    portfolio: str
    ledger_id: str
    ledger_seq: int
    at: object
    source_event_seq: int
    entry_type: str
    order_id: str | None
    execution_id: str | None
    lot_id: str | None
    side: str | None
    quantity: Decimal | None
    reference_price: Decimal | None
    effective_price: Decimal | None
    cash_delta: Decimal
    asset_delta: Decimal
    gross: Decimal
    fee: Decimal
    cash_after: Decimal
    asset_after: Decimal
    fees_after: Decimal
    cost_basis_after: Decimal


    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version not in (3, 4) or (type(self.portfolio) is not str or self.portfolio not in PORTFOLIOS):
            raise ValidationError('Versão/carteira do ledger inválida')
        identifier(self.run_id, 'run_id')
        identifier(self.ledger_id, 'ledger_id')
        integer(self.ledger_seq, 'ledger_seq', 1)
        integer(self.source_event_seq, 'source_event_seq')
        if self.at is not None:
            object.__setattr__(self, 'at', utc(self.at))
        for name in ('cash_delta', 'asset_delta'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValidationError('Delta exige Decimal finito')
        for name in ('gross', 'fee', 'cash_after', 'asset_after', 'fees_after', 'cost_basis_after'):
            decimal_value(getattr(self, name), name, bounded=False)
        if self.entry_type == 'FILL':
            if self.at is None or self.source_event_seq < 1:
                raise ValidationError('Fill sem horário/sequência')
            side_value(self.side)
            for name in ('order_id', 'execution_id', 'lot_id'):
                identifier(getattr(self, name), name)
            for name in ('quantity', 'reference_price', 'effective_price'):
                decimal_value(getattr(self, name), name, positive=True, bounded=False)
        elif self.entry_type != 'INITIAL_BALANCE' or self.source_event_seq != 0 or self.ledger_seq != 1:
            raise ValidationError('Entrada de ledger inválida')
        elif (any(getattr(self, k) is not None for k in ('order_id', 'execution_id', 'lot_id', 'side', 'quantity', 'reference_price', 'effective_price'))
              or any(getattr(self, k) != 0 for k in ('asset_delta', 'gross', 'fee', 'asset_after', 'fees_after', 'cost_basis_after'))
              or self.cash_delta != self.cash_after or self.cash_delta <= 0):
            raise ValidationError('Saldo inicial inválido')


@dataclass(frozen=True)
class Trade:
    trade_id: str
    lot_id: str
    buy_order_id: str
    sell_order_id: str
    buy_execution_id: str
    sell_execution_id: str
    buy_at: object
    sell_at: object
    quantity: Decimal
    buy_reference_price: Decimal
    sell_reference_price: Decimal
    buy_price: Decimal
    sell_price: Decimal
    buy_gross: Decimal
    sell_gross: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    cash_outflow: Decimal
    cash_inflow: Decimal
    net_pnl: Decimal
    duration_seconds: int
    classification: str

    def __post_init__(self):
        for name in ('trade_id', 'lot_id', 'buy_order_id', 'sell_order_id', 'buy_execution_id', 'sell_execution_id'):
            identifier(getattr(self, name), name)
        for name in ('buy_at', 'sell_at'):
            object.__setattr__(self, name, utc(getattr(self, name)))
        for name in ('quantity', 'buy_reference_price', 'sell_reference_price', 'buy_price', 'sell_price'):
            decimal_value(getattr(self, name), name, positive=True, bounded=False)
        for name in ('buy_gross', 'sell_gross', 'buy_fee', 'sell_fee', 'cash_outflow', 'cash_inflow'):
            decimal_value(getattr(self, name), name, bounded=False)
        if not isinstance(self.net_pnl, Decimal) or not self.net_pnl.is_finite():
            raise ValidationError('Resultado exige Decimal finito')
        integer(self.duration_seconds, 'duration_seconds')
        if self.duration_seconds != seconds(self.buy_at, self.sell_at) or self.classification not in ('WIN', 'LOSS', 'BREAK_EVEN'):
            raise ValidationError('Duração/classificação de trade inválida')

    def export(self):
        return {**asdict(self), 'return_pct': percentage(self.net_pnl, self.cash_outflow)}


@dataclass(frozen=True)
class Ledger:
    entries: tuple[Entry, ...]
    trades: tuple[Trade, ...] = ()
    open_fill: Fill | None = None
    open_reference: Decimal | None = None
    realized: Decimal = ZERO
    slippage: Decimal = ZERO
    base_asset: str | None = None

    def __post_init__(self):
        if self.base_asset is not None:
            from .catalog import asset_code
            asset_code(self.base_asset)
            if self.base_asset == 'USDT':
                raise ValidationError('Ativo base deve diferir da cotação')

    @classmethod
    def initial(cls, capital, run_id, portfolio='STRATEGY', at=None, base_asset=None):
        decimal_value(capital, 'capital', positive=True)
        identifier(run_id, 'run_id')
        if type(portfolio) is not str or portfolio not in PORTFOLIOS:
            raise ValidationError('Carteira desconhecida')
        if at is not None:
            at = utc(at)
        entry = Entry(3, run_id, portfolio, f'{portfolio}:initial', 1, at, 0, 'INITIAL_BALANCE',
                      None, None, None, None, None, None, None, capital, ZERO, ZERO, ZERO,
                      capital, ZERO, ZERO, ZERO)
        return cls((entry,), base_asset=base_asset)

    def start(self, at):
        at = utc(at)
        if self.entries[0].at is not None:
            if self.entries[0].at != at:
                raise ValidationError('Inicialização já possui horário')
            return self
        return replace(self, entries=(replace(self.entries[0], at=at), *self.entries[1:]))

    @property
    def balance(self):
        row = self.entries[-1]
        model = AssetBalance if self.base_asset is not None else Balance
        return model(row.cash_after, row.asset_after)

    @property
    def fees(self):
        return self.entries[-1].fees_after

    @property
    def cost_basis(self):
        return self.entries[-1].cost_basis_after

    @financial
    def prepare(self, fill, reference_price, source_event_seq, expected_balance=None):
        if not isinstance(fill, Fill):
            raise ValidationError('Ledger exige Fill')
        decimal_value(reference_price, 'reference_price', positive=True, bounded=False)
        integer(source_event_seq, 'source_event_seq', 1)
        for row in self.entries:
            if row.execution_id == fill.id:
                if (row.order_id, row.side, row.quantity, row.effective_price, row.fee, row.at, row.reference_price) != (
                        fill.order_id, fill.side, fill.quantity, fill.price, fill.fee, fill.at, reference_price):
                    raise ValidationError('ID de ledger conflitante')
                return self
        if self.entries[0].at is None or fill.at < self.entries[-1].at or source_event_seq <= self.entries[-1].source_event_seq:
            raise ValidationError('Movimento fora de ordem ou sem inicialização temporal')
        after = after_fill(self.balance, fill) if expected_balance is None else expected_balance
        gross = fill.price * fill.quantity
        buy = fill.side == 'BUY'
        delta_cash = -(gross + fill.fee) if buy else gross - fill.fee
        delta_asset = fill.quantity if buy else -fill.quantity
        projected = type(self.balance)(self.balance.cash + delta_cash, self.balance.asset_quantity + delta_asset)
        if projected != after:
            raise ValidationError('RECONCILIATION_FAILED: proposta de saldo divergente')
        trades, realized = self.trades, self.realized
        if buy:
            if self.open_fill is not None or self.balance.asset_quantity != 0:
                raise ValidationError('POSITION_OPEN')
            basis, opened, ref = gross + fill.fee, fill, reference_price
            lot_id = f'{fill.id}:lot'
        else:
            opened = self.open_fill
            if opened is None or opened.quantity != fill.quantity:
                raise ValidationError('Venda exige lote integral aberto')
            basis, ref = ZERO, None
            lot_id = f'{opened.id}:lot'
            pnl = gross - fill.fee - self.cost_basis
            trade = Trade(f'{lot_id}:closed', lot_id, opened.order_id, fill.order_id, opened.id, fill.id,
                          opened.at, fill.at, fill.quantity, self.open_reference, reference_price,
                          opened.price, fill.price, opened.price * opened.quantity, gross,
                          opened.fee, fill.fee, self.cost_basis, gross - fill.fee, pnl,
                          seconds(opened.at, fill.at), 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAK_EVEN'))
            trades = (*trades, trade)
            realized += pnl
            opened = None
        impact = (fill.price - reference_price) * fill.quantity if buy else (reference_price - fill.price) * fill.quantity
        row = Entry(3, self.entries[0].run_id, self.entries[0].portfolio,
                    f'{self.entries[0].portfolio}:{fill.id}', len(self.entries)+1, fill.at, source_event_seq,
                    'FILL', fill.order_id, fill.id, lot_id, fill.side, fill.quantity, reference_price,
                    fill.price, delta_cash, delta_asset, gross, fill.fee, after.cash, after.asset_quantity,
                    self.fees + fill.fee, basis)
        return replace(self, entries=(*self.entries, row), trades=trades, open_fill=opened,
                       open_reference=ref, realized=realized, slippage=self.slippage + impact)

    @financial
    def reconcile(self):
        cash = asset = fees = basis = realized = ZERO
        previous_at = None
        previous_source = -1
        ids = set()
        ledger_ids = set()
        closed_ids = set()
        trade_by_sell = {t.sell_execution_id: t for t in self.trades}
        for index, row in enumerate(self.entries, 1):
            if (not isinstance(row, Entry) or row.at is None
                    or (previous_at is not None and row.at < previous_at) or row.ledger_seq != index
                    or row.source_event_seq <= previous_source):
                raise ValidationError('RECONCILIATION_FAILED: sequência do ledger')
            if row.ledger_id in ledger_ids or (row.run_id, row.portfolio) != (self.entries[0].run_id, self.entries[0].portfolio):
                raise ValidationError('RECONCILIATION_FAILED: escopo/ID do ledger')
            ledger_ids.add(row.ledger_id)
            if row.entry_type == 'FILL':
                if row.execution_id in ids or row.gross != row.quantity * row.effective_price:
                    raise ValidationError('RECONCILIATION_FAILED: identidade/bruto')
                ids.add(row.execution_id)
                buy = row.side == 'BUY'
                if (row.cash_delta != (-(row.gross+row.fee) if buy else row.gross-row.fee)
                        or row.asset_delta != (row.quantity if buy else -row.quantity)):
                    raise ValidationError('RECONCILIATION_FAILED: deltas financeiros')
                if buy:
                    if asset != 0:
                        raise ValidationError('RECONCILIATION_FAILED: compra acumulada')
                    basis = row.gross + row.fee
                else:
                    trade = trade_by_sell.get(row.execution_id)
                    pnl = row.gross - row.fee - basis
                    if asset != row.quantity or trade is None or trade.net_pnl != pnl or trade.cash_outflow != basis:
                        raise ValidationError('RECONCILIATION_FAILED: fechamento de lote')
                    realized += pnl
                    basis = ZERO
                    closed_ids.add(row.execution_id)
            elif index != 1:
                raise ValidationError('RECONCILIATION_FAILED: inicialização repetida')
            cash += row.cash_delta
            asset += row.asset_delta
            fees += row.fee
            if (cash, asset, fees, basis) != (row.cash_after, row.asset_after, row.fees_after, row.cost_basis_after):
                raise ValidationError('RECONCILIATION_FAILED: movimentos e saldos')
            previous_at, previous_source = row.at, row.source_event_seq
        if realized != self.realized or closed_ids != set(trade_by_sell) or len(trade_by_sell) != len(self.trades):
            raise ValidationError('RECONCILIATION_FAILED: realizado')
        expected_cost = self.open_fill.price*self.open_fill.quantity+self.open_fill.fee if self.open_fill else ZERO
        if expected_cost != self.cost_basis or (self.open_fill is None) != (asset == 0):
            raise ValidationError('RECONCILIATION_FAILED: base de custo')
        return dict(status='PASSED', reconstructed_cash=cash, reconstructed_asset=asset, reconstructed_fees=fees,
                    cost_basis=self.cost_basis, realized_pnl=self.realized)
