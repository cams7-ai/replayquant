"""Ingestão local, versões e integração real: nenhum teste depende da rede."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal,localcontext,Inexact
import copy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from replayquant.archive import acquire,read_zip,verify_checksum,immutable_file
from replayquant.historical import import_historical,import_path,validate_snapshot,ExportError
from replayquant.historical_models import load_import,RawFile,ImportConfig
from replayquant.historical_adapter import prepare,decimal_canonical
from replayquant.historical_store import connect
from replayquant.provenance import load_provenance,DatasetProvenance
from replayquant.reporting import canonical,manifest,report,wire
from replayquant.shared_config import load_shared
from replayquant.shared_engine import replay_shared,SharedSession,SharedRequest,MINUTE
from replayquant.data import load_inputs,parse_candles
from replayquant.engine import replay
from replayquant.comparison import load_matrix,compare
from replayquant.validation import ValidationError

ROOT=Path(__file__).resolve().parent.parent
D=Decimal


class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.repo=self.path/'store'
        self.config,self.recipe_hash=load_import(ROOT/'experiments/sprint13-importacao-fixture.json')

    def ingest(self,config=None,name='export'):
        out=self.path/name
        q=import_historical(config or self.config,self.repo,out,self.recipe_hash)
        return out,q

    def mutate(self,index,transform):
        files=list(self.config.raw_files);raw=files[index]
        content=read_zip(raw.path.read_bytes(),raw.member).decode()
        text=transform(content)
        folder=self.path/('input'+str(index));folder.mkdir(exist_ok=True)
        target=folder/raw.path.name
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(raw.member,text)
        check=folder/raw.checksum.name
        check.write_text(sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
        files[index]=replace(raw,path=target,checksum=check)
        return replace(self.config,raw_files=tuple(files))

    def count(self,table):
        with sqlite3.connect(self.repo/'catalogo.sqlite') as db:return db.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_fixture_exact_financial_oracle_and_units(self):
        out,q=self.ingest()
        self.assertEqual(q['exit_code'],0)
        self.assertEqual([v['selected'] for v in q['instruments'].values()],[8,8])
        self.assertEqual(sum(f['raw_rows'] for f in q['files']),16)
        s=replay_shared(load_shared(out/'carteira.json'))
        self.assertEqual((s.cash,s.fees,s.exit_code,len(s.fills)),(D('989.95'),D('.05'),0,4))
        self.assertEqual([f['quantity'] for f in s.fills[:2]],[D('.000166'),D('.00420')])
        self.assertEqual(s.fills[0]['at'].isoformat(),'2025-01-01T00:01:00+00:00')
        self.assertEqual(s.fills[-1]['at'].isoformat(),'2025-01-01T00:03:00+00:00')
        with sqlite3.connect(self.repo/'catalogo.sqlite') as db:
            types=db.execute('SELECT DISTINCT typeof(open),typeof(volume),typeof(open_time_us) FROM candle').fetchall()
            self.assertEqual(types,[('text','text','integer')])
            self.assertEqual(db.execute('SELECT count(*) FROM bar_origin WHERE unit="ms"').fetchone()[0],8)
            self.assertEqual(db.execute('SELECT count(*) FROM bar_origin WHERE unit="us"').fetchone()[0],8)
        self.assertEqual(len(list(out.iterdir())),10)
        self.assertEqual(validate_snapshot(out/'manifest.json')['dataset_version'],q['dataset_version'])

    def test_same_import_noop_and_reopen(self):
        a,qa=self.ingest();b,qb=self.ingest(name='again')
        self.assertEqual(self.count('candle'),16);self.assertEqual(self.count('ingestion'),1)
        self.assertEqual(qa['ingestion_id'],qb['ingestion_id'])
        self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},{p.name:p.read_bytes() for p in b.iterdir()})

    def test_permutation_and_equivalent_paths(self):
        a,qa=self.ingest()
        c=replace(self.config,raw_files=tuple(reversed(self.config.raw_files)))
        b,qb=self.ingest(c,'permuted')
        self.assertEqual(qa['dataset_version'],qb['dataset_version'])
        self.assertEqual(qa['ingestion_id'],qb['ingestion_id'])
        self.assertEqual((a/'manifest.json').read_bytes(),(b/'manifest.json').read_bytes())

    def test_duplicate_decimal_scale_has_same_version_new_provenance(self):
        _,original=self.ingest()
        def duplicate(text):
            row=text.splitlines()[0].split(',');row[4]+='.0000'
            return text+','.join(row)+'\n'
        config=self.mutate(0,duplicate)
        _,q=self.ingest(config,'duplicate')
        self.assertEqual(q['dataset_version'],original['dataset_version'])
        self.assertNotEqual(q['ingestion_id'],original['ingestion_id'])
        self.assertEqual(sum(v['duplicates'] for v in q['instruments'].values()),1)
        self.assertEqual(self.count('candle'),16);self.assertEqual(self.count('ingestion'),2)
        self.ingest(config,'duplicate-again');self.assertEqual(self.count('ingestion'),2)

    def test_conflict_rolls_back_entire_batch(self):
        self.ingest()
        def conflict(text):
            row=text.splitlines()[0].split(',');row[2]=row[4]='100001'
            return text+','.join(row)+'\n'
        config=self.mutate(0,conflict)
        with self.assertRaisesRegex(ValidationError,'CANDLE_CONFLICT'):self.ingest(config,'bad')
        self.assertEqual(self.count('dataset_version'),1);self.assertEqual(self.count('ingestion'),1)
        self.assertFalse((self.path/'bad').exists())

    def test_revision_preserves_parent_and_old_snapshot(self):
        old,qa=self.ingest()
        def revision(text):
            rows=text.splitlines();row=rows[0].split(',');row[2]=row[4]='100001';rows[0]=','.join(row)
            return '\n'.join(rows)+'\n'
        c=self.mutate(0,revision)
        with self.assertRaisesRegex(ValidationError,'DATASET_CONFLICT'):self.ingest(c,'no-revision')
        c=replace(c,supersedes=qa['dataset_version'],revision_reason='Correção sintética explícita')
        new,qb=self.ingest(c,'revision')
        self.assertNotEqual(qa['dataset_version'],qb['dataset_version'])
        self.assertEqual(self.count('dataset_version'),2);self.assertEqual(self.count('candle'),32)
        self.assertEqual(replay_shared(load_shared(old/'carteira.json')).cash,D('989.95'))
        self.assertEqual(validate_snapshot(old/'manifest.json')['dataset_version'],qa['dataset_version'])
        with sqlite3.connect(self.repo/'catalogo.sqlite') as db:
            self.assertEqual(db.execute('SELECT parent FROM dataset_version WHERE id=?',(qb['dataset_version'],)).fetchone()[0],qa['dataset_version'])
        with self.assertRaisesRegex(ValidationError,'REVISION_PARENT_INVALID'):
            self.ingest(replace(c,supersedes='a'*64),'bad-parent')

    def test_reverting_a_revision_still_preserves_distinct_lineage(self):
        _,first=self.ingest()
        def change(text):
            rows=text.splitlines();r=rows[0].split(',');r[2]=r[4]='100001';rows[0]=','.join(r)
            return '\n'.join(rows)+'\n'
        c=replace(self.mutate(0,change),supersedes=first['dataset_version'],revision_reason='Correção')
        _,second=self.ingest(c,'second')
        _,third=self.ingest(replace(self.config,supersedes=second['dataset_version'],revision_reason='Restauração explícita'),'third')
        self.assertEqual(len({first['dataset_version'],second['dataset_version'],third['dataset_version']}),3)
        self.assertEqual(self.count('candle'),48)

    def test_real_no_observations_has_null_performance(self):
        c,_=load_import(ROOT/'experiments/sprint13-importacao-real.json')
        out,_=self.ingest(replace(c,as_of=c.window.start))
        data=load_shared(out/'carteira.json');session=replay_shared(data)
        self.assertEqual((session.exit_code,session.cash,len(session.fills)),(2,D(1000),0))
        child=load_inputs(out/'BTCUSDT.json',out/'individual.json',out/'catalog.json',dataset_manifest=out/'manifest.json')
        m=manifest(child);r=report(replay(child.candles,child.config,m['run_id']))
        self.assertEqual(r['exit_code'],2)
        self.assertEqual(r['analysis']['metrics']['portfolio_return_pct']['value'],None)

    def test_json_strict_and_manifest_content_validation(self):
        path=self.path/'invalid.json'
        for text in ['{"schema_version":1,"schema_version":1}', '{"schema_version":true}', '{"schema_version":NaN}']:
            path.write_text(text)
            with self.assertRaises(ValidationError):load_import(path)
        out,_=self.ingest()
        m=json.loads((out/'manifest.json').read_bytes());m['dataset_version']='a'*64
        (out/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValidationError):load_provenance(out/'manifest.json')

    def test_acquisition_failure_reports_partial_not_complete(self):
        with patch('replayquant.archive.fetch',side_effect=OSError('offline')):
            with self.assertRaises(OSError):acquire(ROOT/'experiments/sprint13-aquisicao-real.json',self.path/'failed-download')
        receipt=json.loads((self.path/'failed-download/acquisition.json').read_text())
        self.assertEqual(receipt['status'],'INCOMPLETE')
        self.assertTrue((self.path/'failed-download/INCOMPLETE').exists())

    def test_sql_failure_does_not_accept_a_prefix(self):
        with patch('replayquant.historical_store.insert_candles',side_effect=sqlite3.OperationalError('injected')):
            with self.assertRaises(sqlite3.OperationalError):self.ingest()
        self.assertEqual(self.count('dataset_version'),0);self.assertEqual(self.count('candle'),0)
        self.assertGreater(len(list((self.repo/'objects').iterdir())),0)
        self.ingest(name='retry');self.assertEqual(self.count('candle'),16)

    def test_corrupt_last_file_never_opens_database(self):
        c=self.mutate(3,lambda text:text+'invalid\n')
        with self.assertRaises(ValidationError):self.ingest(c)
        self.assertFalse((self.repo/'catalogo.sqlite').exists())

    def test_export_failure_keeps_commit_and_incomplete(self):
        original=Path.write_bytes
        def fail(path,data):
            if path.name=='ETHUSDT.json':raise OSError('injected')
            return original(path,data)
        with patch.object(Path,'write_bytes',fail):
            with self.assertRaisesRegex(ExportError,'EXPORT_FAILED'):self.ingest()
        self.assertEqual(self.count('dataset_version'),1)
        self.assertTrue((self.path/'export/INCOMPLETE').exists())
        self.assertFalse((self.path/'export/manifest.json').exists())
        self.ingest(name='retry');self.assertEqual(self.count('candle'),16)

    def test_existing_output_precedes_commit(self):
        (self.path/'export').mkdir()
        with self.assertRaises(ValidationError):self.ingest()
        self.assertFalse((self.repo/'catalogo.sqlite').exists())

    def test_wrong_unit_close_order_columns_and_volumes(self):
        files=list(self.config.raw_files);files[0]=replace(files[0],timestamp_unit='us')
        with self.assertRaisesRegex(ValidationError,'TIMESTAMP_UNIT_MISMATCH'):prepare(replace(self.config,raw_files=tuple(files)))
        transforms=[lambda t:t.replace('1735689419999','1735689419998'),
                    lambda t:'\n'.join(reversed(t.splitlines()))+'\n',
                    lambda t:t+'1,2\n',lambda t:t.replace(',4,0,0,0',',4,2,0,0'),
                    lambda t:t.replace('100000','NaN',1),lambda t:t.replace('100000','100000.0000000000001',1)]
        for transform in transforms:
            with self.subTest(transform=transform),self.assertRaises(ValidationError):prepare(self.mutate(0,transform))

    def test_checksum_crc_and_zip_traversal(self):
        raw=self.config.raw_files[0]
        with self.assertRaises(ValidationError):verify_checksum(raw.path.read_bytes(),b'0'*64+b'  other.zip',raw.path.name)
        for name in ['../'+raw.member,'/'+raw.member,raw.member+'/x']:
            stream=BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:archive.writestr(name,'test')
            with self.assertRaises(ValidationError):read_zip(stream.getvalue(),raw.member)
        with self.assertRaises(ValidationError):read_zip(b'notzip',raw.member)
        blob=bytearray(raw.path.read_bytes());pos=blob.find(b'PK\x01\x02');blob[pos+16]^=1
        with self.assertRaises(ValidationError):read_zip(bytes(blob),raw.member)

    def test_incomplete_cutoff_and_global_gap_prefix(self):
        cutoff=self.config.window.end-timedelta(seconds=30)
        out,q=self.ingest(replace(self.config,as_of=cutoff))
        self.assertEqual(q['exit_code'],2)
        self.assertEqual([v['incomplete'] for v in q['instruments'].values()],[1,1])
        data=load_shared(out/'carteira.json');s=replay_shared(data)
        self.assertEqual(s.exit_code,1)
        self.assertEqual(len(s.evaluations),14)
        self.assertTrue(s.interrupted)

    def test_gap_does_not_consume_other_asset_open(self):
        c=self.mutate(1,lambda t:'\n'.join(row for i,row in enumerate(t.splitlines()) if i!=1)+'\n')
        out,q=self.ingest(c)
        self.assertEqual(q['exit_code'],2)
        s=replay_shared(load_shared(out/'carteira.json'))
        self.assertEqual(s.at.isoformat(),'2025-01-01T00:01:00+00:00')
        self.assertEqual(s.exit_code,1);self.assertEqual(len(s.fills),0)
        self.assertGreater(s.reserved_cash(),D(30))
        self.assertFalse(any(e['phase']=='OPEN_MARKS' and e['at']==s.at for e in s.events))

    def test_temporal_universe_and_open_lot_after_delisting(self):
        catalog=json.loads(self.config.catalog_raw);universe=json.loads(self.config.universe_raw)
        start='2024-12-31T23:58:00+00:00';end='2025-01-01T00:02:00+00:00'
        for row in catalog['instruments']:
            if row['symbol']=='ETHUSDT':row.update(available_from=start,available_until=end)
        for row in universe['instruments']:
            if row['symbol']=='ETHUSDT':row.update(available_from=start,available_until=end)
        from replayquant.catalog import parse_catalog
        raw=canonical(catalog);c=replace(self.config,catalog=parse_catalog(raw),catalog_raw=raw,universe_raw=canonical(universe))
        out,q=self.ingest(c)
        self.assertEqual(q['instruments']['ETHUSDT']['selected'],4)
        self.assertEqual(q['instruments']['ETHUSDT']['outside_availability'],4)
        self.assertFalse(any(i['reason']=='DATA_GAP' for i in q['issues']))
        data=load_shared(out/'carteira.json');session=SharedSession(data.config)
        for i in range(9):
            at=data.config.window.start+i*MINUTE
            cs=[c for _,stream in data.datasets for c in stream if c.close_time==at]
            os=[c.opening() for _,stream in data.datasets for c in stream if c.open_time==at]
            requests=(SharedRequest('controlled-entry','ema','ETHUSDT','BUY'),) if i==3 else ()
            session.on_boundary(at,cs,os,requests)
        session.finish()
        lot=session.own_lot('ema','ETHUSDT')
        self.assertIsNotNone(lot);self.assertEqual(lot['protection_status'],'INSTRUMENT_UNAVAILABLE')
        self.assertGreater(session.assets['ETH'],0);self.assertEqual(session.reserves[lot['reservation_id']]['status'],'RELEASED')

    def test_no_observations_quality_is_reportable(self):
        out,q=self.ingest(replace(self.config,as_of=self.config.window.start))
        self.assertEqual(q['exit_code'],2);self.assertTrue(all(v['selected']==0 for v in q['instruments'].values()))
        self.assertEqual(validate_snapshot(out/'manifest.json')['status'],'QUALITY_WARNINGS')

    def test_context_canonical_numbers_and_python_numeric_order(self):
        with localcontext() as ctx:
            ctx.prec=3;ctx.traps[Inexact]=True
            out,_=self.ingest()
            self.assertEqual(replay_shared(load_shared(out/'carteira.json')).cash,D('989.95'))
            self.assertEqual(ctx.prec,3)
        self.assertEqual([decimal_canonical(D(v)) for v in ['0.000','9.00','10.0','100.000']],['0','9','10','100'])
        values=['100','9','10'];self.assertNotEqual(sorted(values),sorted(values,key=D))

    def test_api_and_json_reject_invalid_types(self):
        for kwargs in [dict(as_of=self.config.as_of.replace(tzinfo=None)),dict(raw_files=list(self.config.raw_files)),
                       dict(source='BINANCE_SPOT'),dict(supersedes='a'*64),dict(catalog_raw=b'{}')]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValidationError):replace(self.config,**kwargs)
        with self.assertRaises(ValidationError):DatasetProvenance(b'{}',())
        with self.assertRaises(ValidationError):RawFile('BTCUSDT',Path('x.zip'),'../x',True,Path('x'))
        with self.assertRaises(ValidationError):prepare(None)

    def test_unknown_database_version_is_not_recreated(self):
        self.repo.mkdir()
        with sqlite3.connect(self.repo/'catalogo.sqlite') as db:db.execute('PRAGMA user_version=99')
        with self.assertRaises(ValidationError):self.ingest()
        with sqlite3.connect(self.repo/'catalogo.sqlite') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],99)

    def test_real_snapshot_requires_provenance_and_no_bank_or_network(self):
        c,_=load_import(ROOT/'experiments/sprint13-importacao-real.json')
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network')):
            out,q=self.ingest(c)
            data=load_shared(out/'carteira.json');s=replay_shared(data)
            self.assertEqual(s.config.source,'BINANCE_SPOT');self.assertEqual(q['exit_code'],0)
            self.assertTrue(all(e['source']=='BINANCE_SPOT' for e in s.events))
            individual=load_inputs(out/'BTCUSDT.json',out/'individual.json',out/'catalog.json',dataset_manifest=out/'manifest.json')
            result=report(replay(individual.candles,individual.config))
            self.assertEqual(result['provenance'][0]['universe']['restriction'],'SURVIVORSHIP_RESTRICTION')
            self.assertNotIn('Dados fictícios',str(result['limitations']))
            with self.assertRaises(ValidationError):load_inputs(out/'BTCUSDT.json',out/'individual.json',out/'catalog.json')
            value=json.loads((out/'carteira.json').read_text())
            for d in value['datasets']:d.pop('manifest')
            (out/'missing.json').write_text(json.dumps(value))
            with self.assertRaises(ValidationError):load_shared(out/'missing.json')
            # Export alone is portable: database can be removed from the execution path.
            (self.repo/'catalogo.sqlite').rename(self.repo/'unavailable.sqlite')
            self.assertEqual(replay_shared(load_shared(out/'carteira.json')).cash,s.cash)
            self.assertEqual(len(load_matrix(out/'matriz.json').children),4)

    def test_manifest_mismatch_foreign_event_and_rollback(self):
        c,_=load_import(ROOT/'experiments/sprint13-importacao-real.json');out,_=self.ingest(c)
        p=load_provenance(out/'manifest.json');data=load_shared(out/'carteira.json');s=SharedSession(data.config)
        candle=dict(data.datasets)['BTCUSDT'][0];before=canonical(s.events)
        with self.assertRaises(ValidationError):s.on_boundary(candle.open_time,[],[replace(candle.opening(),price=D(1))])
        self.assertEqual(canonical(s.events),before)
        with self.assertRaises(ValidationError):p.verify('ETHUSDT',(out/'BTCUSDT.json').read_bytes(),c.catalog)
        (out/'BTCUSDT.json').write_text('{}')
        with self.assertRaises(ValidationError):load_provenance(out/'manifest.json')

    def test_acquisition_is_explicit_mocked_and_immutable(self):
        recipe=ROOT/'experiments/sprint13-aquisicao-real.json'
        def fetch(url,limit):
            name=url.rsplit('/',1)[-1];file=ROOT/'data/fixtures/sprint13'/name
            return file.read_bytes(),url
        with patch('replayquant.archive.fetch',side_effect=fetch):
            receipt=acquire(recipe,self.path/'download')
        self.assertEqual(receipt['exit_code'],0);self.assertEqual(len(receipt['objects']),4)
        target=self.path/'blob';immutable_file(target,b'a');immutable_file(target,b'a')
        with self.assertRaises(ValidationError):immutable_file(target,b'b')
        self.assertEqual(target.read_bytes(),b'a')

    def test_four_formats_and_other_cwd(self):
        out,_=self.ingest()
        import os
        for fmt in ('texto','json','markdown','html'):
            proc=subprocess.run([sys.executable,'-m','replayquant','validar-dados','--manifesto',str(out/'manifest.json'),'--formato',fmt],
                                cwd=self.path,env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr);self.assertIn('FICTICIA',proc.stdout)


if __name__=='__main__':unittest.main()
