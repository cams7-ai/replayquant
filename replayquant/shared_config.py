"""Receitas schema 7 e configuração imutável da carteira compartilhada."""
from dataclasses import dataclass, fields as dc_fields
from fractions import Fraction
from decimal import Decimal
from pathlib import Path
from hashlib import sha256
import re

from .catalog import Catalog, Window, load_catalog, parse_window
from .data import parse_candles, parse_strategy
from .risk_models import RiskParameters
from .strategy_models import StrategySpec
from .validation import ValidationError, decimal_value, decimal_text, fields, strict_json


@dataclass(frozen=True)
class PortfolioLimits:
    exposure_fraction: Decimal
    max_open_risk_fraction: Decimal
    daily_loss_fraction: Decimal
    drawdown_fraction: Decimal
    max_price_age_seconds: Decimal

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = decimal_value(getattr(self, name), name, positive=True)
            if name != 'max_price_age_seconds' and value > 1:
                raise ValidationError('Fração de carteira excede 1')


@dataclass(frozen=True)
class Allocation:
    id: str
    priority: int
    allocation_fraction: Decimal
    symbols: tuple[str, ...]
    strategy: StrategySpec
    risk: RiskParameters

    def __post_init__(self):
        if (type(self.id) is not str or re.fullmatch(r'[a-zA-Z0-9_-]+', self.id) is None
                or self.id == 'UNALLOCATED'):
            raise ValidationError('ID de titular inválido ou reservado')
        if type(self.priority) is not int or self.priority < 0:
            raise ValidationError('Prioridade exige inteiro >= 0')
        if decimal_value(self.allocation_fraction, 'allocation_fraction', positive=True) > 1:
            raise ValidationError('Alocação excede 1')
        if (type(self.symbols) is not tuple or not self.symbols
                or any(type(s) is not str for s in self.symbols)
                or len(set(self.symbols)) != len(self.symbols)):
            raise ValidationError('Symbols exige tuple única não vazia')
        if not isinstance(self.strategy, StrategySpec) or not isinstance(self.risk, RiskParameters):
            raise ValidationError('Estratégia e risco devem ser tipados')
        object.__setattr__(self, 'symbols', tuple(sorted(self.symbols)))


@dataclass(frozen=True)
class SharedConfig:
    catalog: Catalog
    window: Window
    initial_cash: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    portfolio: PortfolioLimits
    instrument_limits: tuple[tuple[str, object], ...]
    strategies: tuple[Allocation, ...]
    source: str = 'FICTICIA'
    quote_asset: str = 'USDT'
    interval: str = '1m'
    mode: str = 'SHARED_PORTFOLIO'
    signal_policy: str = 'ALLOCATED_BUDGETS_V1'
    schema_version: int = 7
    provenance: tuple = ()

    def __post_init__(self):
        if (not isinstance(self.catalog, Catalog) or not isinstance(self.window, Window)
                or not isinstance(self.portfolio, PortfolioLimits)):
            raise ValidationError('Carteira exige catálogo, janela e limites tipados')
        if self.source not in ('FICTICIA', 'BINANCE_SPOT') or (self.quote_asset, self.interval, self.mode, self.signal_policy) != (
                'USDT', '1m', 'SHARED_PORTFOLIO', 'ALLOCATED_BUDGETS_V1'):
            raise ValidationError('Política/identidade de carteira inválida')
        if type(self.schema_version) is not int or self.schema_version != 7:
            raise ValidationError('schema_version exige inteiro 7')
        decimal_value(self.initial_cash, 'initial_cash', positive=True)
        for name in ('fee_rate', 'slippage_rate'):
            if decimal_value(getattr(self, name), name) >= 1:
                raise ValidationError('Custo exige [0, 1)')
        if (type(self.strategies) is not tuple or not self.strategies
                or not all(isinstance(s, Allocation) for s in self.strategies)):
            raise ValidationError('Estratégias exigem tuple de Allocation')
        if len({s.id for s in self.strategies}) != len(self.strategies):
            raise ValidationError('Titular duplicado')
        if sum((Fraction(s.allocation_fraction) for s in self.strategies), Fraction()) > 1:
            raise ValidationError('Soma das alocações excede 1')
        if (type(self.instrument_limits) is not tuple or not self.instrument_limits
                or any(type(x) is not tuple or len(x) != 2 or type(x[0]) is not str
                       for x in self.instrument_limits)):
            raise ValidationError('Limites exigem tuple de pares símbolo/fração')
        symbols = {symbol for s in self.strategies for symbol in s.symbols}
        if (len(dict(self.instrument_limits)) != len(self.instrument_limits)
                or set(dict(self.instrument_limits)) != symbols):
            raise ValidationError('Limites e bindings devem corresponder sem duplicatas')
        for symbol, fraction in self.instrument_limits:
            item = self.catalog.resolve(self.source, symbol, self.interval)
            if item.quote_asset != self.quote_asset or decimal_value(fraction, 'limite', positive=True) > 1:
                raise ValidationError('Limite/cotação inválido')
        object.__setattr__(self, 'strategies', tuple(sorted(self.strategies, key=lambda s: (s.priority, s.id))))
        object.__setattr__(self, 'instrument_limits', tuple(sorted(self.instrument_limits)))
        if self.source == 'BINANCE_SPOT':
            from .provenance import DatasetProvenance
            if (type(self.provenance) is not tuple or not self.provenance
                    or not all(isinstance(p, DatasetProvenance) for p in self.provenance)):
                raise ValidationError('BINANCE_SPOT exige proveniência tipada')
            for symbol in symbols:
                if not any(p.identity['source'] == self.source and symbol+'.json' in dict(p.files)
                           and p.identity['universe']['source'] == self.source for p in self.provenance):
                    raise ValidationError('Proveniência sem binding')
                p = next(p for p in self.provenance if symbol+'.json' in dict(p.files))
                p.verify(symbol, dict(p.files)[symbol+'.json'], self.catalog)
        elif self.provenance != ():
            raise ValidationError('Proveniência histórica exige BINANCE_SPOT')

    def instrument(self, symbol):
        return self.catalog.resolve(self.source, symbol, self.interval)


@dataclass(frozen=True)
class SharedInputs:
    config: SharedConfig
    datasets: tuple
    data_hashes: tuple
    recipe_hash: str
    coverage: tuple


def model_decimals(value, model):
    fields(value, {f.name for f in dc_fields(model)}, model.__name__)
    return model(**{k: decimal_text(v, k) for k, v in value.items()})


def load_shared(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = strict_json(raw)
    fields(value, {'schema_version', 'mode', 'source', 'quote_asset', 'interval', 'catalog',
                   'window', 'initial_cash', 'fee_rate', 'slippage_rate', 'signal_policy',
                   'portfolio', 'instrument_limits', 'datasets', 'strategies'}, 'carteira')
    if type(value['catalog']) is not str or not value['catalog']:
        raise ValidationError('catalog exige caminho')
    catalog = load_catalog(path.parent / value['catalog'])
    if type(value['strategies']) is not list or type(value['datasets']) is not list:
        raise ValidationError('strategies/datasets exigem listas')
    allocations = []
    for row in value['strategies']:
        fields(row, {'id', 'priority', 'allocation_fraction', 'symbols', 'strategy', 'risk'}, 'titular')
        if type(row['symbols']) is not list:
            raise ValidationError('symbols exige lista')
        allocations.append(Allocation(row['id'], row['priority'], decimal_text(row['allocation_fraction'], 'alocação'),
                                      tuple(row['symbols']), parse_strategy(row['strategy']),
                                      model_decimals(row['risk'], RiskParameters)))
    if type(value['instrument_limits']) is not dict:
        raise ValidationError('instrument_limits exige objeto')
    limits = []
    for symbol, row in value['instrument_limits'].items():
        fields(row, {'exposure_fraction'}, 'limite de instrumento')
        limits.append((symbol, decimal_text(row['exposure_fraction'], 'exposure_fraction')))
    provenances = {}
    if value['source'] == 'BINANCE_SPOT':
        from .provenance import load_provenance
        for row in value['datasets']:
            fields(row, {'symbol','path','manifest'}, 'dataset histórico')
            if type(row['manifest']) is not str or not row['manifest']:
                raise ValidationError('manifest exige caminho')
            p = load_provenance(path.parent/row['manifest'])
            provenances[p.identity['ingestion_id']] = p
    config = SharedConfig(catalog, parse_window(value['window']),
                          *(decimal_text(value[k], k) for k in ('initial_cash', 'fee_rate', 'slippage_rate')),
                          model_decimals(value['portfolio'], PortfolioLimits), tuple(limits), tuple(allocations),
                          **{k: value[k] for k in ('source', 'quote_asset', 'interval', 'mode', 'signal_policy', 'schema_version')},
                          provenance=tuple(provenances[k] for k in sorted(provenances)))
    datasets, hashes, coverage = {}, [], []
    for row in value['datasets']:
        fields(row, {'symbol', 'path'} | ({'manifest'} if config.source == 'BINANCE_SPOT' else set()), 'dataset')
        symbol = row['symbol']
        if type(symbol) is not str or symbol in datasets or symbol not in dict(limits) or type(row['path']) is not str:
            raise ValidationError('Dataset duplicado ou sem binding/caminho')
        data = (path.parent / row['path']).read_bytes()
        if config.source == 'BINANCE_SPOT':
            load_provenance(path.parent/row['manifest']).verify(symbol, data, catalog)
        candles, diagnostics = parse_candles(data, contiguous=False, catalog=catalog, allow_empty=config.source=='BINANCE_SPOT')
        if any((c.source, c.symbol, c.interval) != (config.source, symbol, config.interval) for c in candles):
            raise ValidationError('Dataset deve conter somente seu instrumento')
        item = config.instrument(symbol)
        eligible = tuple(c for c in candles if config.window.contains(c.open_time, c.close_time)
                         and item.contains(c.open_time, c.close_time))
        datasets[symbol] = eligible
        hashes.append((symbol, sha256(data).hexdigest()))
        coverage.append(dict(symbol=symbol, accepted=len(eligible), excluded=len(candles)-len(eligible),
                             duplicates=len(diagnostics), available_from=item.available_from,
                             available_until=item.available_until, requested_window=config.window,
                             reason=None if eligible else 'INSTRUMENT_UNAVAILABLE'))
    if set(datasets) != set(dict(limits)):
        raise ValidationError('Datasets devem corresponder a todos os bindings')
    return SharedInputs(config, tuple(sorted(datasets.items())), tuple(sorted(hashes)),
                        sha256(raw).hexdigest(), tuple(sorted(coverage, key=lambda c: c['symbol'])))
