"""Proveniência verificada de snapshot portátil, sem dependência do SQLite/rede."""
from dataclasses import dataclass
from pathlib import Path
from .archive import digest
from .reporting import canonical
from .validation import ValidationError,fields,strict_json,version


@dataclass(frozen=True)
class DatasetProvenance:
    manifest_raw: bytes
    files: tuple[tuple[str,bytes],...]

    def __post_init__(self):
        try:
            self._validate()
        except (KeyError,TypeError,ValueError) as exc:
            raise ValidationError('Proveniência inválida: '+str(exc)) from exc

    def _validate(self):
        if type(self.manifest_raw) is not bytes or type(self.files) is not tuple or any(
                type(x) is not tuple or len(x)!=2 or type(x[0]) is not str or type(x[1]) is not bytes for x in self.files):
            raise ValidationError('Proveniência exige bytes tipados')
        m=strict_json(self.manifest_raw)
        fields(m,{'schema_version','dataset_version','ingestion_id','logical','code_hash','files','datasets',
                  'source','raw_files','policy','supersedes','revision_reason'},'manifesto histórico')
        version(m['schema_version'])
        if type(m['files']) is not dict or len(dict(self.files))!=len(self.files) or set(dict(self.files))!=set(m['files']):
            raise ValidationError('MANIFEST_FILES_MISMATCH')
        for name,raw in self.files:
            if Path(name).name!=name or digest(raw)!=m['files'][name]:
                raise ValidationError('MANIFEST_HASH_MISMATCH: '+name)
        if digest(canonical(m['logical']))!=m['dataset_version']:
            raise ValidationError('DATASET_VERSION_MISMATCH')
        expected=digest(canonical(dict(dataset_version=m['dataset_version'],code_hash=m['code_hash'],files=m['raw_files'],
                                       supersedes=m['supersedes'],revision_reason=m['revision_reason'])))
        if expected!=m['ingestion_id']:
            raise ValidationError('INGESTION_ID_MISMATCH')
        files=dict(self.files)
        if m['logical']['catalog_hash']!=digest(files['catalog.json']) or m['logical']['universe_hash']!=digest(files['universe.json']):
            raise ValidationError('MANIFEST_CATALOG_MISMATCH')
        if m['source']!=m['logical']['source'] or m['policy']!=m['logical']['policy']:
            raise ValidationError('MANIFEST_SOURCE_MISMATCH')
        if type(m['datasets']) is not dict or set(m['datasets'])!=set(m['logical']['normalized']):
            raise ValidationError('MANIFEST_DATASET_MISMATCH')
        for symbol,name in m['datasets'].items():
            if name not in files or digest(files[name])!=m['logical']['normalized'][symbol]:
                raise ValidationError('MANIFEST_DATASET_MISMATCH')
        quality=strict_json(files['quality.json'])
        if (quality['dataset_version'],quality['ingestion_id'],quality['files'])!=(m['dataset_version'],m['ingestion_id'],m['raw_files']):
            raise ValidationError('MANIFEST_QUALITY_MISMATCH')
        from .catalog import parse_catalog, parse_window
        from .data import parse_candles
        from .validation import datetime_text
        catalog=parse_catalog(files['catalog.json'])
        window=parse_window(m['logical']['window'])
        cutoff=datetime_text(m['logical']['as_of'],'as_of')
        if (quality['source']!=m['source'] or quality['dataset_kind']!=m['logical']['dataset_kind']
                or quality['universe']!=strict_json(files['universe.json'])
                or quality['status']!=('QUALITY_WARNINGS' if quality['issues'] else 'PASSED')
                or quality['exit_code']!=(2 if quality['issues'] else 0)):
            raise ValidationError('MANIFEST_QUALITY_MISMATCH')
        for symbol,name in m['datasets'].items():
            candles,duplicates=parse_candles(files[name],contiguous=False,catalog=catalog,allow_empty=True)
            if (duplicates or len(candles)!=quality['instruments'][symbol]['selected']
                    or any(c.source!=m['source'] or c.symbol!=symbol or not window.contains(c.open_time,c.close_time)
                           or c.close_time>cutoff or not catalog.resolve(c.source,symbol,c.interval).contains(c.open_time,c.close_time)
                           for c in candles)):
                raise ValidationError('MANIFEST_CANDLES_MISMATCH')

    @property
    def identity(self):
        m=strict_json(self.manifest_raw)
        q=strict_json(dict(self.files)['quality.json'])
        return dict(dataset_version=m['dataset_version'],ingestion_id=m['ingestion_id'],source=m['source'],
                    manifest_hash=digest(self.manifest_raw),policy=m['policy'],quality_status=q['status'],
                    universe=strict_json(dict(self.files)['universe.json']))

    def __replayquant_wire__(self):
        return self.identity

    def verify(self,symbol,data,catalog):
        m=strict_json(self.manifest_raw)
        if (symbol not in m['datasets'] or digest(data)!=m['logical']['normalized'][symbol]
                or catalog.content_hash!=m['logical']['catalog_hash']):
            raise ValidationError('PROVENANCE_BINDING_MISMATCH')
        if catalog.resolve(m['source'],symbol,'1m').source!=m['source']:
            raise ValidationError('PROVENANCE_SOURCE_MISMATCH')

    def verify_event(self,event):
        m=strict_json(self.manifest_raw)
        if event.symbol not in m['datasets']:
            raise ValidationError('PROVENANCE_BINDING_MISMATCH')
        from .data import parse_candles
        from .catalog import parse_catalog
        candles,_=parse_candles(dict(self.files)[m['datasets'][event.symbol]],contiguous=False,
                                catalog=parse_catalog(dict(self.files)['catalog.json']))
        from .models import Candle
        expected=next((c for c in candles if c.open_time==(event.open_time if isinstance(event,Candle) else event.at)),None)
        if expected is None or (expected if isinstance(event,Candle) else expected.opening())!=event:
            raise ValidationError('PROVENANCE_EVENT_MISMATCH')


def load_provenance(path):
    path=Path(path);raw=path.read_bytes();m=strict_json(raw)
    if type(m) is not dict or type(m.get('files')) is not dict:
        raise ValidationError('Manifesto inválido')
    data=[]
    for name in sorted(m['files']):
        if Path(name).name!=name or name in ('','.', '..'):
            raise ValidationError('Manifesto com caminho inválido')
        data.append((name,(path.parent/name).read_bytes()))
    try:
        return DatasetProvenance(raw,tuple(data))
    except (KeyError,TypeError,ValueError) as exc:
        raise ValidationError('Manifesto inconsistente: '+str(exc)) from exc


def enrich_historical(summary,provenances):
    identities=[p.identity for p in provenances]
    summary['provenance']=identities
    summary['limitations']=[line.replace('Dados fictícios','Dados históricos públicos') for line in summary['limitations']]
    summary['limitations']=list(summary['limitations'])+[
        'FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE: sem histórico de revisões disponível na época.',
        'OBSERVED_COVERAGE_ONLY / SURVIVORSHIP_RESTRICTION: universo limitado à amostra observada.',
        'Filtros, taxa e slippage são hipóteses locais, não regras históricas conhecidas da Binance.']
    return summary
