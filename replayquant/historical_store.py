"""Publicação transacional SQLite de snapshots imutáveis, sem SQL financeiro."""
from pathlib import Path
import sqlite3
from .archive import immutable_file,digest
from .historical_adapter import microseconds,decimal_canonical
from .reporting import canonical
from .validation import ValidationError

DDL='''
CREATE TABLE dataset (dataset_key TEXT PRIMARY KEY, kind TEXT NOT NULL);
CREATE TABLE dataset_version (id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL REFERENCES dataset,
 parent TEXT REFERENCES dataset_version, revision_reason TEXT, window TEXT NOT NULL, logical TEXT NOT NULL);
CREATE TABLE raw_object (sha256 TEXT PRIMARY KEY, size INTEGER NOT NULL, path TEXT NOT NULL);
CREATE TABLE ingestion (id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES dataset_version,
 recipe_hash TEXT NOT NULL, code_hash TEXT NOT NULL, quality TEXT NOT NULL);
CREATE TABLE ingestion_file (ingestion_id TEXT REFERENCES ingestion, symbol TEXT, member TEXT,
 raw_sha256 TEXT REFERENCES raw_object, checksum_sha256 TEXT REFERENCES raw_object, unit TEXT,
 PRIMARY KEY(ingestion_id,symbol,member));
CREATE TABLE candle (version_id TEXT REFERENCES dataset_version, source TEXT, symbol TEXT, open_time_us INTEGER,
 close_time_us INTEGER, open TEXT, high TEXT, low TEXT, close TEXT, volume TEXT, market TEXT,
 PRIMARY KEY(version_id,source,symbol,open_time_us));
CREATE TABLE bar_origin (ingestion_id TEXT REFERENCES ingestion, symbol TEXT, open_time_us INTEGER,
 raw_sha256 TEXT REFERENCES raw_object, member TEXT, line INTEGER, duplicate INTEGER, source_open INTEGER,
 source_close INTEGER, unit TEXT, PRIMARY KEY(ingestion_id,raw_sha256,member,line));
CREATE TABLE instrument (version_id TEXT REFERENCES dataset_version, symbol TEXT, snapshot TEXT,
 PRIMARY KEY(version_id,symbol));
CREATE TABLE universe_evidence (version_id TEXT PRIMARY KEY REFERENCES dataset_version, snapshot TEXT);
CREATE TABLE quality_issue (ingestion_id TEXT REFERENCES ingestion, issue_seq INTEGER, payload TEXT,
 PRIMARY KEY(ingestion_id,issue_seq));
'''


def connect(path):
    connection=sqlite3.connect(path)
    connection.execute('PRAGMA foreign_keys=ON')
    version=connection.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0,1):
        connection.close();raise ValidationError('DATABASE_VERSION_UNSUPPORTED')
    if version==0:
        tables=connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if tables:
            connection.close();raise ValidationError('DATABASE_VERSION_UNSUPPORTED: banco não vazio')
        try:
            connection.executescript('BEGIN IMMEDIATE;'+DDL+'PRAGMA user_version=1;COMMIT;')
        except BaseException:
            connection.close();raise
    return connection


def insert_candles(db,batch):
    for symbol,candles in batch['selected'].items():
        for candle,aux in zip(candles,batch['auxiliary'][symbol]):
            db.execute('INSERT INTO candle VALUES (?,?,?,?,?,?,?,?,?,?,?)',(
                batch['dataset_version'],candle.source,symbol,microseconds(candle.open_time),microseconds(candle.close_time),
                *(decimal_canonical(getattr(candle,k)) for k in ('open','high','low','close','volume')),
                canonical(aux).decode()))


def commit_batch(repository,batch,recipe_hash):
    repo=Path(repository);repo.mkdir(parents=True,exist_ok=True)
    # Objects can be orphaned after failure; only committed DB relations accept them.
    for sha,raw in batch['objects'].items():
        immutable_file(repo/'objects'/sha,raw)
    c=batch['config'];v=batch['dataset_version'];ing=batch['ingestion_id']
    db=connect(repo/'catalogo.sqlite')
    try:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT dataset_key,window,logical FROM dataset_version WHERE id=?',(v,)).fetchone()
        window=canonical(c.window).decode()
        if c.supersedes is not None:
            parent=db.execute('SELECT dataset_key,window FROM dataset_version WHERE id=?',(c.supersedes,)).fetchone()
            if parent!=(c.dataset_key,window) or c.supersedes==v:
                raise ValidationError('REVISION_PARENT_INVALID')
        versions=db.execute('SELECT id FROM dataset_version WHERE dataset_key=?',(c.dataset_key,)).fetchall()
        if not existing and versions and c.supersedes is None:
            raise ValidationError('DATASET_CONFLICT: revisão explícita obrigatória')
        db.execute('INSERT OR IGNORE INTO dataset VALUES (?,?)',(c.dataset_key,c.dataset_kind))
        if db.execute('SELECT kind FROM dataset WHERE dataset_key=?',(c.dataset_key,)).fetchone()[0]!=c.dataset_kind:
            raise ValidationError('DATASET_CONFLICT: tipo divergente')
        if not existing:
            db.execute('INSERT INTO dataset_version VALUES (?,?,?,?,?,?)',(v,c.dataset_key,c.supersedes,c.revision_reason,window,canonical(batch['logical']).decode()))
            insert_candles(db,batch)
            for i in c.catalog.instruments:
                db.execute('INSERT INTO instrument VALUES (?,?,?)',(v,i.symbol,canonical(i).decode()))
            db.execute('INSERT INTO universe_evidence VALUES (?,?)',(v,c.universe_raw.decode()))
        elif existing[2]!=canonical(batch['logical']).decode():
            raise ValidationError('VERSION_CONTENT_CONFLICT')
        for sha,raw in batch['objects'].items():
            db.execute('INSERT OR IGNORE INTO raw_object VALUES (?,?,?)',(sha,len(raw),'objects/'+sha))
        if not db.execute('SELECT 1 FROM ingestion WHERE id=?',(ing,)).fetchone():
            db.execute('INSERT INTO ingestion VALUES (?,?,?,?,?)',(ing,v,recipe_hash,batch['code_hash'],canonical(batch['quality']).decode()))
            for file in batch['quality']['files']:
                db.execute('INSERT INTO ingestion_file VALUES (?,?,?,?,?,?)',(ing,file['symbol'],file['member'],file['sha256'],file['checksum_sha256'],file['timestamp_unit']))
            for origin in batch['origins']:
                db.execute('INSERT INTO bar_origin VALUES (?,?,?,?,?,?,?,?,?,?)',(
                    ing,origin['symbol'],origin['open_time_us'],origin['raw_sha256'],origin['member'],origin['line'],int(origin['duplicate']),origin['source_open'],origin['source_close'],origin['timestamp_unit']))
            for i,issue in enumerate(batch['quality']['issues']):
                db.execute('INSERT INTO quality_issue VALUES (?,?,?)',(ing,i,canonical(issue).decode()))
        db.commit()
    except BaseException:
        db.rollback();raise
    finally:
        db.close()
    return v,ing
