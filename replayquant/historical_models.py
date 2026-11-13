"""Contratos tipados de importação; caminhos não participam da identidade lógica."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from .catalog import Catalog, Window, load_catalog, parse_window
from .validation import ValidationError, fields, strict_json, version, datetime_text, utc
from .archive import digest


@dataclass(frozen=True)
class RawFile:
    symbol: str
    path: Path
    member: str
    timestamp_unit: str
    checksum: Path

    def __post_init__(self):
        if (type(self.symbol) is not str or re.fullmatch('[A-Z0-9]+USDT',self.symbol) is None
                or self.timestamp_unit not in ('ms','us') or type(self.timestamp_unit) is not str
                or not isinstance(self.path,Path) or not isinstance(self.checksum,Path)
                or type(self.member) is not str or not self.member.startswith(self.symbol+'-1m-')
                or self.path.name != self.member.removesuffix('.csv')+'.zip'):
            raise ValidationError('Arquivo bruto inválido')


@dataclass(frozen=True)
class ImportConfig:
    dataset_key: str
    dataset_kind: str
    source: str
    catalog: Catalog
    catalog_raw: bytes
    universe_raw: bytes
    window: Window
    as_of: datetime
    raw_files: tuple[RawFile,...]
    supersedes: str | None = None
    revision_reason: str | None = None
    adapter: str = 'BINANCE_SPOT_KLINES_CSV_V1'
    input_order: str = 'REQUIRE_ASCENDING_PER_FILE'
    quote_asset: str = 'USDT'
    interval: str = '1m'

    def __post_init__(self):
        if type(self.dataset_key) is not str or re.fullmatch('[A-Za-z0-9_-]+',self.dataset_key) is None:
            raise ValidationError('dataset_key inválido')
        if (self.dataset_kind,self.source) not in (('PUBLIC_HISTORICAL','BINANCE_SPOT'),('SYNTHETIC_FORMAT_FIXTURE','FICTICIA')):
            raise ValidationError('Origem/tipo de dataset divergentes')
        if (self.adapter,self.input_order,self.quote_asset,self.interval) != (
                'BINANCE_SPOT_KLINES_CSV_V1','REQUIRE_ASCENDING_PER_FILE','USDT','1m'):
            raise ValidationError('Política de importação inválida')
        if (not isinstance(self.catalog,Catalog) or not isinstance(self.window,Window)
                or type(self.catalog_raw) is not bytes or digest(self.catalog_raw) != self.catalog.content_hash
                or type(self.universe_raw) is not bytes):
            raise ValidationError('Catálogo/janela/evidências tipados obrigatórios')
        from .catalog import parse_catalog
        if parse_catalog(self.catalog_raw) != self.catalog:
            raise ValidationError('Catálogo não corresponde aos bytes')
        object.__setattr__(self,'as_of',utc(self.as_of))
        if (type(self.raw_files) is not tuple or not self.raw_files
                or not all(isinstance(f,RawFile) for f in self.raw_files)):
            raise ValidationError('raw_files exige tuple de RawFile')
        identities=[(r.symbol,r.member) for r in self.raw_files]
        if {r.symbol for r in self.raw_files} != {'BTCUSDT','ETHUSDT'}:
            raise ValidationError('Esta importação exige BTCUSDT e ETHUSDT')
        if len(identities)!=len(set(identities)):
            raise ValidationError('Arquivo duplicado na receita')
        for raw in self.raw_files:
            self.catalog.resolve(self.source,raw.symbol,self.interval)
        if (self.supersedes is None)!=(self.revision_reason is None):
            raise ValidationError('Revisão exige pai e justificativa')
        if self.supersedes is not None and (type(self.supersedes) is not str or re.fullmatch('[a-f0-9]{64}',self.supersedes) is None
                                           or type(self.revision_reason) is not str or not self.revision_reason.strip()):
            raise ValidationError('Revisão inválida')
        u=strict_json(self.universe_raw)
        fields(u,{'schema_version','source','basis','restriction','reference','as_of','instruments'},'universo')
        version(u['schema_version'])
        expected='OBSERVED_COVERAGE_ONLY' if self.source=='BINANCE_SPOT' else 'SYNTHETIC_FIXTURE'
        if (u['source']!=self.source or u['basis']!=expected or type(u['reference']) is not str or not u['reference']
                or u['restriction']!=('SURVIVORSHIP_RESTRICTION' if self.source=='BINANCE_SPOT' else None)):
            raise ValidationError('Evidência de universo incompatível')
        datetime_text(u['as_of'],'universe.as_of')
        if type(u['instruments']) is not list or not u['instruments']:
            raise ValidationError('Universo sem instrumentos')
        seen=set()
        for row in u['instruments']:
            fields(row,{'symbol','available_from','available_until'},'evidência')
            if type(row['symbol']) is not str or row['symbol'] in seen:
                raise ValidationError('Evidência duplicada/inválida')
            seen.add(row['symbol']);i=self.catalog.resolve(self.source,row['symbol'],self.interval)
            if (datetime_text(row['available_from'],'from')!=i.available_from
                    or (datetime_text(row['available_until'],'until') if row['available_until'] else None)!=i.available_until):
                raise ValidationError('Disponibilidade diverge da evidência')
        if seen!={r.symbol for r in self.raw_files}:
            raise ValidationError('Universo e arquivos devem corresponder')


def load_import(path):
    path=Path(path);raw=path.read_bytes();v=strict_json(raw)
    fields(v,{'schema_version','mode','adapter','dataset_key','dataset_kind','source','quote_asset','interval','catalog',
              'universe_evidence','window','as_of','input_order','supersedes','revision_reason','raw_files'},'importação')
    version(v['schema_version'])
    if v['mode']!='HISTORICAL_IMPORT' or type(v['raw_files']) is not list:
        raise ValidationError('Modo/lista de importação inválidos')
    for key in ('catalog','universe_evidence'):
        if type(v[key]) is not str or not v[key]:
            raise ValidationError('Caminho obrigatório')
    catalog_path=path.parent/v['catalog'];catalog=load_catalog(catalog_path)
    files=[]
    for row in v['raw_files']:
        fields(row,{'symbol','path','member','timestamp_unit','checksum'},'arquivo')
        if any(type(row[k]) is not str or not row[k] for k in ('path','checksum')):
            raise ValidationError('Caminho bruto obrigatório')
        files.append(RawFile(row['symbol'],path.parent/row['path'],row['member'],row['timestamp_unit'],path.parent/row['checksum']))
    values={k:v[k] for k in ('dataset_key','dataset_kind','source','supersedes','revision_reason','adapter','input_order','quote_asset','interval')}
    return ImportConfig(**values,catalog=catalog,catalog_raw=catalog_path.read_bytes(),
                        universe_raw=(path.parent/v['universe_evidence']).read_bytes(),window=parse_window(v['window']),
                        as_of=datetime_text(v['as_of'],'as_of'),raw_files=tuple(files)),digest(raw)
