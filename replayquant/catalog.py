"""Snapshot local de instrumentos e disponibilidade, sem consultas externas."""
from dataclasses import dataclass, fields as dataclass_fields
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
from .risk_models import InstrumentFilters
from .validation import ValidationError, identifier, utc, strict_json, fields, version, datetime_text, decimal_text


def asset_code(value):
    if type(value) is not str or re.fullmatch(r'[A-Z0-9]{1,30}', value) is None:
        raise ValidationError('Código de moeda/símbolo inválido')
    return value


def minute(value):
    value = utc(value)
    if value.second or value.microsecond:
        raise ValidationError('Horário deve estar alinhado ao minuto')
    return value


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def __post_init__(self):
        object.__setattr__(self, 'start', minute(self.start))
        object.__setattr__(self, 'end', minute(self.end))
        if self.start >= self.end:
            raise ValidationError('Janela exige início anterior ao fim')

    def contains(self, opening, closing):
        return self.start <= opening and closing <= self.end


def parse_window(value):
    fields(value, {'start', 'end'}, 'window')
    return Window(*(datetime_text(value[k], k) for k in ('start', 'end')))


@dataclass(frozen=True)
class Instrument:
    source: str
    symbol: str
    base_asset: str
    quote_asset: str
    intervals: tuple[str, ...]
    available_from: datetime
    available_until: datetime | None
    instrument_filters: InstrumentFilters
    rules_basis: str
    rules_as_of: datetime
    rules_source: str

    def __post_init__(self):
        if self.source != 'FICTICIA' or type(self.source) is not str:
            raise ValidationError('Origem suportada: FICTICIA')
        for value in (self.symbol, self.base_asset, self.quote_asset):
            asset_code(value)
        if self.quote_asset != 'USDT' or self.base_asset == self.quote_asset or self.symbol != self.base_asset + self.quote_asset:
            raise ValidationError('Moedas/símbolo incompatíveis; cotação exige USDT')
        if type(self.intervals) is not tuple or self.intervals != ('1m',):
            raise ValidationError('Intervalos suportados: tuple de 1m')
        object.__setattr__(self, 'available_from', minute(self.available_from))
        if self.available_until is not None:
            object.__setattr__(self, 'available_until', minute(self.available_until))
            if self.available_until <= self.available_from:
                raise ValidationError('Disponibilidade inválida')
        if not isinstance(self.instrument_filters, InstrumentFilters):
            raise ValidationError('Filtros exigem InstrumentFilters')
        if type(self.rules_basis) is not str or self.rules_basis not in ('SYNTHETIC_ASSUMPTION', 'CURRENT_RULES_ASSUMED_FOR_PERIOD'):
            raise ValidationError('Hipótese das regras inválida')
        object.__setattr__(self, 'rules_as_of', utc(self.rules_as_of))
        identifier(self.rules_source, 'rules_source')

    def contains(self, opening, closing):
        return self.available_from <= opening and (self.available_until is None or closing <= self.available_until)


@dataclass(frozen=True)
class Catalog:
    catalog_id: str
    instruments: tuple[Instrument, ...]
    content_hash: str

    def __post_init__(self):
        identifier(self.catalog_id, 'catalog_id')
        if type(self.instruments) is not tuple or not self.instruments or not all(isinstance(i, Instrument) for i in self.instruments):
            raise ValidationError('Catálogo exige instrumentos tipados')
        keys = [(i.source, i.symbol) for i in self.instruments]
        if len(keys) != len(set(keys)):
            raise ValidationError('Instrumento duplicado no catálogo')
        if type(self.content_hash) is not str or re.fullmatch(r'[0-9a-f]{64}', self.content_hash) is None:
            raise ValidationError('Hash de catálogo inválido')

    def resolve(self, source, symbol, interval):
        for item in self.instruments:
            if (item.source, item.symbol) == (source, symbol) and interval in item.intervals:
                return item
        raise ValidationError('Instrumento/intervalo ausente do catálogo')


def parse_catalog(raw):
    value = strict_json(raw)
    fields(value, {'schema_version', 'catalog_id', 'instruments'}, 'catálogo')
    version(value['schema_version'])
    if type(value['instruments']) is not list:
        raise ValidationError('instruments exige lista')
    result = []
    for row in value['instruments']:
        fields(row, {f.name for f in dataclass_fields(Instrument)}, 'instrumento')
        item = dict(row)
        if type(item['intervals']) is not list:
            raise ValidationError('intervals exige lista')
        item['intervals'] = tuple(item['intervals'])
        for key in ('available_from', 'rules_as_of'):
            item[key] = datetime_text(item[key], key)
        if item['available_until'] is not None:
            item['available_until'] = datetime_text(item['available_until'], 'available_until')
        filters = item['instrument_filters']
        fields(filters, {'step', 'min_quantity', 'min_notional'}, 'instrument_filters')
        item['instrument_filters'] = InstrumentFilters(**{k: decimal_text(v, k) for k, v in filters.items()})
        result.append(Instrument(**item))
    return Catalog(value['catalog_id'], tuple(result), sha256(raw).hexdigest())


def load_catalog(path):
    return parse_catalog(Path(path).read_bytes())
