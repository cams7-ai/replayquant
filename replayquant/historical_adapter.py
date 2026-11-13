"""Normalização local integral, anterior ao recorte e a qualquer transação SQLite."""
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
import re
from .archive import digest, verify_checksum, read_zip
from .historical_models import ImportConfig
from .models import Candle
from .reporting import canonical, wire
from .validation import ValidationError, decimal_text, financial

EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)
MINUTE=timedelta(minutes=1)
POLICY='FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE'


def decimal_canonical(value):
    text=format(value,'f')
    return text.rstrip('0').rstrip('.') if '.' in text and value else ('0' if not value else text)


def integer(text):
    if type(text) is not str or re.fullmatch('[0-9]+',text) is None:
        raise ValidationError('Inteiro CSV inválido')
    try:
        value=int(text)
        if value>9223372036854775807:
            raise ValueError()
        return value
    except ValueError as exc:
        raise ValidationError('Inteiro fora da faixa') from exc


def microseconds(at):
    delta=at-EPOCH
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def parse_row(row, raw, source):
    if len(row)!=12:
        raise ValidationError('CSV_COLUMNS: esperadas 12 colunas')
    scale=1000 if raw.timestamp_unit=='ms' else 1
    op,cl=integer(row[0]),integer(row[6])
    try:
        at=EPOCH+timedelta(microseconds=op*scale)
        end=EPOCH+timedelta(microseconds=(cl+1)*scale)
    except OverflowError as exc:
        raise ValidationError('TIMESTAMP_UNIT_MISMATCH') from exc
    day=raw.member[-14:-4]
    if at.date().isoformat()!=day or at.second or at.microsecond or end-at!=MINUTE:
        raise ValidationError('TIMESTAMP_UNIT_MISMATCH: data/alinhamento/fim inclusivo')
    values={key:Decimal(decimal_canonical(decimal_text(row[index],key))) for key,index in
            [('open',1),('high',2),('low',3),('close',4),('volume',5),('quote_volume',7),('taker_base',9),('taker_quote',10),('ignored',11)]}
    trades=integer(row[8])
    candle=Candle(source,raw.symbol,'1m',at,end,*(values[k] for k in ('open','high','low','close','volume')),True)
    if (values['taker_base']>candle.volume or values['taker_quote']>values['quote_volume']
            or (not candle.volume and any(values[k] for k in ('quote_volume','taker_base','taker_quote')))):
        raise ValidationError('VOLUME_INVALID')
    aux={k:decimal_canonical(values[k]) for k in ('quote_volume','taker_base','taker_quote','ignored')}
    aux['trades']=trades
    return candle,aux


@financial
def prepare(config):
    if not isinstance(config,ImportConfig):
        raise ValidationError('API exige ImportConfig')
    records={}; origins=[];files=[];objects={};issues=[]
    stats={s:dict(raw_rows=0,duplicates=0,incomplete=0,before_window=0,after_window=0,outside_availability=0)
           for s in sorted({r.symbol for r in config.raw_files})}
    for raw in sorted(config.raw_files,key=lambda r:(r.symbol,r.member)):
        data=raw.path.read_bytes();check=raw.checksum.read_bytes()
        verify_checksum(data,check,raw.path.name)
        csv_raw=read_zip(data,raw.member)
        sha=digest(data);check_sha=digest(check)
        objects[sha]=data;objects[check_sha]=check
        file=dict(symbol=raw.symbol,member=raw.member,timestamp_unit=raw.timestamp_unit,sha256=sha,
                  checksum_sha256=check_sha,size=len(data),raw_rows=0,duplicates=0,incomplete=0)
        previous=None
        try:
            reader=csv.reader(StringIO(csv_raw.decode('utf-8'),newline=''),strict=True)
            for line,row in enumerate(reader,1):
                candle,aux=parse_row(row,raw,config.source)
                key=(raw.symbol,candle.open_time)
                semantic=canonical(dict(candle=wire(candle),market=aux))
                file['raw_rows']+=1;stats[raw.symbol]['raw_rows']+=1
                duplicate=key in records
                if duplicate:
                    if records[key][2]!=semantic:
                        raise ValidationError('CANDLE_CONFLICT: '+str(key))
                    file['duplicates']+=1;stats[raw.symbol]['duplicates']+=1
                else:
                    if previous is not None and candle.open_time<previous:
                        raise ValidationError('INPUT_OUT_OF_ORDER')
                    previous=candle.open_time
                    records[key]=(candle,aux,semantic)
                origins.append(dict(symbol=raw.symbol,open_time_us=microseconds(candle.open_time),raw_sha256=sha,
                                    member=raw.member,line=line,duplicate=duplicate,
                                    source_open=integer(row[0]),source_close=integer(row[6]),timestamp_unit=raw.timestamp_unit))
                if candle.close_time>config.as_of:
                    file['incomplete']+=1
                    if not duplicate:
                        stats[raw.symbol]['incomplete']+=1
                        issues.append(dict(reason='CANDLE_NOT_FINAL',symbol=raw.symbol,open_time=candle.open_time))
        except (UnicodeError,csv.Error) as exc:
            raise ValidationError('CSV_INVALID') from exc
        files.append(file)
    selected={s:[] for s in stats}; auxiliary={s:[] for s in stats}; classification={}
    for (symbol,_),(candle,aux,_) in sorted(records.items()):
        st=stats[symbol];instrument=config.catalog.resolve(config.source,symbol,'1m')
        if candle.close_time>config.as_of:
            classification[symbol,candle.open_time]='incomplete'
            continue
        if candle.open_time<config.window.start:
            st['before_window']+=1;classification[symbol,candle.open_time]='before_window';continue
        if candle.close_time>config.window.end:
            st['after_window']+=1;classification[symbol,candle.open_time]='after_window';continue
        if not instrument.contains(candle.open_time,candle.close_time):
            st['outside_availability']+=1;classification[symbol,candle.open_time]='outside_availability';continue
        classification[symbol,candle.open_time]='selected'
        selected[symbol].append(candle);auxiliary[symbol].append(dict(open_time=candle.open_time,**aux))
    file_map={(f['symbol'],f['member']):f for f in files}
    for file in files:
        file.update(selected=0,before_window=0,after_window=0,outside_availability=0)
    for origin in origins:
        if not origin['duplicate']:
            category=classification[origin['symbol'],EPOCH+timedelta(microseconds=origin['open_time_us'])]
            if category!='incomplete':
                file_map[origin['symbol'],origin['member']][category]+=1
    for symbol in stats:
        st=stats[symbol];cs=selected[symbol];instrument=config.catalog.resolve(config.source,symbol,'1m')
        expected=[];at=config.window.start
        while at<config.window.end:
            if instrument.contains(at,at+MINUTE):expected.append(at)
            at+=MINUTE
        present={c.open_time for c in cs};missing=[at for at in expected if at not in present]
        issues.extend(dict(reason='DATA_GAP',symbol=symbol,open_time=at) for at in missing)
        if not cs:issues.append(dict(reason='NO_ELIGIBLE_CANDLES',symbol=symbol,open_time=None))
        st.update(unique_rows=sum(1 for sym,_ in records if sym==symbol),selected=len(cs),expected=len(expected),
                  missing_openings=missing,first=cs[0].open_time if cs else None,last=cs[-1].close_time if cs else None,
                  available_from=instrument.available_from,available_until=instrument.available_until)
    normalized={s:canonical(dict(schema_version=1,candles=cs))+b'\n' for s,cs in selected.items()}
    quality=dict(schema_version=1,source=config.source,dataset_kind=config.dataset_kind,adapter=config.adapter,
                 window=config.window,as_of=config.as_of,status='QUALITY_WARNINGS' if issues else 'PASSED',
                 exit_code=2 if issues else 0,policy=POLICY,files=files,instruments=stats,issues=issues,
                 universe=__import__('json').loads(config.universe_raw),
                 limitations=['Custos/filtros são hipóteses sintéticas; USDT não é USD.',
                              'Arquivo final não reconstrói revisões disponíveis em tempo real.',
                              'Qualidade não comprova rentabilidade ou execução realista.'])
    logical=dict(schema_version=1,dataset_key=config.dataset_key,dataset_kind=config.dataset_kind,source=config.source,
                 adapter=config.adapter,policy=POLICY,window=config.window,as_of=config.as_of,
                 catalog_hash=digest(config.catalog_raw),universe_hash=digest(config.universe_raw),
                 normalized={s:digest(v) for s,v in normalized.items()},market=auxiliary)
    if config.supersedes is not None:
        logical.update(supersedes=config.supersedes,revision_reason=config.revision_reason)
    version=digest(canonical(logical))
    code_hash=digest(Path_bytes())
    ingestion=digest(canonical(dict(dataset_version=version,code_hash=code_hash,files=files,
                                    supersedes=config.supersedes,revision_reason=config.revision_reason)))
    return dict(config=config,selected=selected,auxiliary=auxiliary,normalized=normalized,objects=objects,origins=origins,
                quality=quality,logical=logical,dataset_version=version,ingestion_id=ingestion,code_hash=code_hash)


def Path_bytes():
    from pathlib import Path
    root=Path(__file__).parent
    return b''.join((root/name).read_bytes() for name in ('archive.py','historical_models.py','historical_adapter.py','historical_store.py'))
