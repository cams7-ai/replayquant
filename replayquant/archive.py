"""Única fronteira de rede: arquivos públicos oficiais, íntegros e limitados."""
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit
import zipfile
import zlib
import os
import tempfile

from .reporting import json_text
from .validation import ValidationError, fields, strict_json, version

BASE = 'https://data.binance.vision/data/spot/daily/klines'
MAX_ZIP = 10*1024*1024
MAX_EXPANDED = 100*1024*1024


def digest(raw):
    return sha256(raw).hexdigest()


def verify_checksum(raw, checksum, filename):
    try:
        match = re.fullmatch(r'([a-fA-F0-9]{64})[ \t]+\*?([^\r\n]+)\s*', checksum.decode('ascii'))
    except UnicodeError as exc:
        raise ValidationError('CHECKSUM_INVALID') from exc
    if not match or match[2] != filename or match[1].lower() != digest(raw):
        raise ValidationError('CHECKSUM_MISMATCH')


def read_zip(raw, member):
    if len(raw) > MAX_ZIP or type(member) is not str or re.fullmatch(r'[A-Z0-9]+-1m-\d{4}-\d{2}-\d{2}\.csv', member) is None:
        raise ValidationError('ZIP_INVALID_MEMBER')
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            if (len(infos) != 1 or infos[0].filename != member or infos[0].is_dir()
                    or infos[0].flag_bits & 1 or infos[0].file_size > MAX_EXPANDED
                    or (infos[0].external_attr >> 16) & 0o170000 == 0o120000):
                raise ValidationError('ZIP_UNSAFE')
            with archive.open(member) as stream:
                data = stream.read(MAX_EXPANDED+1)
                if len(data) > MAX_EXPANDED:
                    raise ValidationError('ZIP_TOO_LARGE')
            return data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise ValidationError('ZIP_INVALID_CRC_OR_FORMAT') from exc


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https' or urlsplit(newurl).netloc != 'data.binance.vision':
            raise ValidationError('REDIRECT_NOT_AUTHORIZED')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit):
    if urlsplit(url).scheme != 'https' or urlsplit(url).netloc != 'data.binance.vision':
        raise ValidationError('URL_NOT_AUTHORIZED')
    opener = urllib.request.build_opener(OfficialRedirect())
    for attempt in range(3):
        try:
            with opener.open(url, timeout=30) as response:
                data = response.read(limit+1)
                if len(data) > limit:
                    raise ValidationError('DOWNLOAD_TOO_LARGE')
                return data, response.url
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(attempt+1)


def immutable_file(path, raw):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValidationError('SOURCE_REVISION_DETECTED: '+path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(raw)
        try:
            os.link(temporary,path)
        except FileExistsError:
            if path.read_bytes()!=raw:
                raise ValidationError('SOURCE_REVISION_DETECTED: '+path.name)
    finally:
        os.unlink(temporary)


def acquire(config_path, destination):
    value = strict_json(Path(config_path).read_bytes())
    fields(value, {'schema_version','mode','provider','market','source','interval','symbols','dates','base_url'}, 'aquisição')
    version(value['schema_version'])
    if tuple(value[k] for k in ('mode','provider','market','source','interval','base_url')) != (
            'PUBLIC_ARCHIVE_DOWNLOAD','BINANCE_PUBLIC_DATA','SPOT','BINANCE_SPOT','1m',BASE):
        raise ValidationError('Aquisição pública não autorizada')
    for key in ('symbols','dates'):
        if (type(value[key]) is not list or not value[key] or any(type(x) is not str for x in value[key])
                or len(set(value[key])) != len(value[key])):
            raise ValidationError('Lista de aquisição inválida')
    if any(s not in ('BTCUSDT','ETHUSDT') for s in value['symbols']):
        raise ValidationError('Símbolo não autorizado para aquisição')
    for day in value['dates']:
        try:
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError()
        except ValueError as exc:
            raise ValidationError('Data de aquisição inválida') from exc
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    marker = dest/'INCOMPLETE'
    marker.write_text('Aquisição incompleta\n')
    receipt = dict(schema_version=1, source='BINANCE_SPOT', status='INCOMPLETE', objects=[],
                   reference='https://github.com/binance/binance-public-data',
                   terms='https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md')
    try:
        for symbol in sorted(value['symbols']):
            for day in sorted(value['dates']):
                name=f'{symbol}-1m-{day}.zip'
                url=f'{BASE}/{symbol}/1m/{name}'
                check, check_url=fetch(url+'.CHECKSUM',4096)
                raw, final_url=fetch(url,MAX_ZIP)
                verify_checksum(raw,check,name)
                read_zip(raw,name[:-4]+'.csv')
                # Verification is complete before publishing either original object.
                immutable_file(dest/name,raw)
                immutable_file(dest/(name+'.CHECKSUM'),check)
                receipt['objects'].append(dict(name=name,url=url,final_url=final_url,checksum_url=check_url,
                                               sha256=digest(raw),checksum_sha256=digest(check),size=len(raw),status='VERIFIED',
                                               fetched_at=datetime.now(timezone.utc).isoformat()))
        receipt.update(status='COMPLETED',exit_code=0)
        marker.unlink()
    finally:
        (dest/'acquisition.json').write_text(json_text(receipt),encoding='utf-8')
    return receipt
