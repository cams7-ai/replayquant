"""Catálogo, isolamento por instrumento, fronteiras e matriz independente."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.catalog import load_catalog, parse_catalog, Catalog, Window
from replayquant.catalog_config import CatalogConfig
from replayquant.comparison import load_matrix, compare, write_comparison, rank
from replayquant.data import load_inputs, parse_config
from replayquant.engine import replay
from replayquant.html_report import html_report
from replayquant.reporting import canonical, manifest, report, write_artifacts
from replayquant.risk_engine import RiskSession
from replayquant.risk_models import RiskRequest
from replayquant.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT/'data/catalogo/sprint11-instrumentos.json'
CONFIG = ROOT/'experiments/sprint11-eth-rsi.json'
DATA = ROOT/'data/fixtures/sprint11-eth-candles.json'
MATRIX = ROOT/'experiments/sprint11-matriz.json'


def inputs(catalog=None):
    return load_inputs(DATA, CONFIG, catalog=catalog or load_catalog(CATALOG))


def changed_catalog(**values):
    catalog = load_catalog(CATALOG)
    eth = replace(catalog.instruments[1], **values)
    return replace(catalog, instruments=(catalog.instruments[0], eth))


class CatalogTests(unittest.TestCase):
    def test_catalog_strict_json_and_python_models(self):
        raw = json.loads(CATALOG.read_text())
        variants = []
        for key, value in [('base_asset','BTC'), ('quote_asset','USD'), ('intervals',['5m']),
                           ('available_until','2026-01-01T12:00:00Z'), ('available_from','2026-01-01T12:00:01Z'),
                           ('rules_basis','HISTORICAL_VERIFIED'), ('rules_source',''), ('rules_as_of','2026-01-01')]:
            bad = deepcopy(raw);bad['instruments'][1][key] = value;variants.append(bad)
        bad=deepcopy(raw);bad['instruments'].append(bad['instruments'][0]);variants.append(bad)
        bad=deepcopy(raw);bad['instruments'][1]['instrument_filters']['step']=True;variants.append(bad)
        bad=deepcopy(raw);bad['instruments'][1]['extra']='x';variants.append(bad)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_catalog(json.dumps(value).encode())
        with self.assertRaises(ValidationError):parse_catalog(b'{"schema_version":1,"schema_version":1}')
        catalog=load_catalog(CATALOG)
        with self.assertRaises(ValidationError):replace(catalog,instruments=(*catalog.instruments,catalog.instruments[0]))
        with self.assertRaises(ValidationError):Window(catalog.instruments[0].available_from,catalog.instruments[0].available_from)
        with self.assertRaises(ValidationError):replace(catalog.instruments[1],available_from=True)
        current=changed_catalog(rules_basis='CURRENT_RULES_ASSUMED_FOR_PERIOD')
        self.assertEqual(inputs(current).config.instrument.rules_basis,'CURRENT_RULES_ASSUMED_FOR_PERIOD')

    def test_schema6_and_legacy_catalog_boundaries(self):
        raw=json.loads(CONFIG.read_text())
        with self.assertRaises(ValidationError):parse_config(CONFIG.read_bytes())
        with self.assertRaises(ValidationError):load_inputs(ROOT/'data/fixtures/sprint10-candles.json',ROOT/'experiments/sprint10-sma.json',CATALOG)
        for key,value in [('mode','MANUAL'), ('symbol','SOLUSDT'), ('instrument_filters',{}), ('orders',[])]:
            bad={**raw,key:value}
            with self.assertRaises(ValidationError):parse_config(json.dumps(bad).encode(),catalog=load_catalog(CATALOG))
        i=inputs()
        with self.assertRaises(ValidationError):replace(i.config,window=None)
        with self.assertRaises(ValidationError):replace(i.config,instrument_filters=replace(i.config.instrument_filters,step=D('1')))
        with self.assertRaises(ValidationError):manifest(i,analysis=False)
        self.assertEqual(manifest(i),manifest(i,analysis=True))

    def test_identity_contains_catalog_even_unused_records(self):
        i=inputs()
        catalog=replace(i.config.catalog,instruments=(replace(i.config.catalog.instruments[0],rules_source='Outra hipótese'),i.config.instrument))
        changed=replace(i,config=replace(i.config,catalog=catalog))
        self.assertNotEqual(manifest(i)['run_id'],manifest(changed)['run_id'])
        self.assertEqual(manifest(i)['catalog'].content_hash,i.config.catalog.content_hash)

    def test_third_instrument_requires_only_catalog_and_data(self):
        i=inputs();sol=replace(i.config.instrument,symbol='SOLUSDT',base_asset='SOL')
        catalog=replace(i.config.catalog,instruments=(*i.config.catalog.instruments,sol))
        config=replace(i.config,catalog=catalog,symbol='SOLUSDT')
        candles=tuple(replace(c,symbol='SOLUSDT') for c in i.candles)
        s=replay(candles,config);p=report(s)
        self.assertEqual(s.balance.cash,D('999.96012'))
        self.assertEqual(p['base_asset'],'SOL')
        self.assertFalse(hasattr(s.balance,'btc'))
        self.assertIn('USDT/SOL',html_report(p))
        self.assertTrue(any(r.currency=='SOL' for r in s.ledger.reservations))


class InstrumentReplayTests(unittest.TestCase):
    def test_financial_units_and_individual_child_parity(self):
        matrix=load_matrix(MATRIX)
        _,summary,runs=compare(matrix)
        self.assertEqual(summary['exit_code'],2)
        self.assertEqual(len(runs),6)
        for name,metadata,s,p in runs:
            self.assertEqual(p['schema_version'],6)
            self.assertEqual(p['coverage']['status'],'FULL')
            if name.startswith('rsi'):
                expected='999.9602' if s.config.base_asset=='BTC' else '999.96012'
                self.assertEqual(s.balance.cash,D(expected))
                self.assertEqual(p['exit_code'],0)
                self.assertEqual(s.balance.asset_quantity,0)
            else:
                self.assertEqual(s.balance.cash,D('980.06008'))
                self.assertEqual(p['analysis']['metrics']['final_gross_equity']['value'],D('993.34008'))
                self.assertEqual(p['exit_code'],2)
            self.assertEqual(p['analysis']['reconciliation']['status'],'PASSED')
            self.assertEqual(p['analysis']['benchmarks'][1]['portfolio'],'BUY_HOLD_ASSET')
            self.assertEqual(p['analysis']['metrics']['final_asset_quantity']['unit'],s.config.base_asset)
            self.assertTrue(all(e['schema_version']==6 for e in s.events))
        i=inputs();metadata=manifest(i);s=replay(i.candles,i.config,metadata['run_id'])
        child=next(run for run in runs if run[0].startswith('rsi') and run[2].config.symbol=='ETHUSDT')
        self.assertEqual(metadata,child[1])
        self.assertEqual(canonical(s.events),canonical(child[2].events))
        self.assertEqual(canonical(report(s)),canonical(child[3]))
        eligible=[r for r in summary['rows'] if r['rank'] is not None]
        self.assertEqual([(r['symbol'],r['rank']) for r in eligible],[('BTCUSDT',1),('ETHUSDT',2)])

    def test_partial_availability_warmup_and_btc_unchanged(self):
        _,full,full_runs=compare(load_matrix(MATRIX))
        _,partial,runs=compare(load_matrix(ROOT/'experiments/sprint11-matriz-parcial.json'))
        for row in partial['rows']:
            if row['symbol']=='ETHUSDT':
                self.assertEqual(row['coverage']['accepted_candles'],4)
                self.assertEqual(row['coverage']['status'],'PARTIAL')
                self.assertIsNone(row['rank'])
                s=next(s for name,_,s,p in runs if name==row['strategy_id'] and s.config.symbol=='ETHUSDT')
                self.assertEqual(s.strategy.indicator.count,4)
                self.assertEqual(s.fills,())
            else:
                original=next(r for r in full['rows'] if r['symbol']==row['symbol'] and r['strategy_id']==row['strategy_id'])
                self.assertEqual(canonical(row['metrics']),canonical(original['metrics']))

    def test_no_eligible_data_has_null_performance_and_eleven_artifacts(self):
        original=inputs()
        catalog=changed_catalog(available_from=original.config.window.end+timedelta(days=1))
        i=inputs(catalog);metadata=manifest(i);s=replay(i.candles,i.config,metadata['run_id']);p=report(s)
        self.assertEqual(p['status'],'UNAVAILABLE')
        self.assertEqual(p['exit_code'],2)
        self.assertEqual(s.events,[])
        self.assertEqual(s.balance.cash,D(1000))
        self.assertIsNone(p['analysis']['metrics']['portfolio_return_pct']['value'])
        self.assertEqual(p['analysis']['metrics']['portfolio_return_pct']['reason'],'NO_ELIGIBLE_CANDLES')
        with tempfile.TemporaryDirectory() as path:
            write_artifacts(Path(path)/'run',metadata,s,p)
            self.assertEqual(len(list((Path(path)/'run').iterdir())),11)
            self.assertIn('UNAVAILABLE',html_report(p))

    def test_availability_end_keeps_open_position_and_releases_reserve(self):
        original=inputs();end=original.candles[4].close_time
        i=inputs(changed_catalog(available_until=end));s=replay(i.candles,i.config);p=report(s)
        self.assertGreater(s.balance.asset_quantity,0)
        self.assertEqual(len(s.fills),1)
        self.assertEqual(s.ledger.entries[-1].asset_reserved_after,0)
        self.assertEqual(p['coverage']['observed_until'],end)
        self.assertEqual(p['coverage']['status'],'PARTIAL')
        self.assertEqual(s.protection_groups[-1].status,'ENDED_WITH_OPEN_POSITION')
        i=inputs(changed_catalog(available_until=original.config.window.end))
        matrix_child=next(child for name,child in load_matrix(MATRIX).children if name=='sma-2-3' and child.config.symbol=='ETHUSDT')
        config=replace(matrix_child.config,catalog=i.config.catalog)
        s=replay(i.candles,config)
        self.assertEqual(s.orders[-1].reason,'INSTRUMENT_UNAVAILABLE')

    def test_last_valid_bar_can_resolve_protection_at_end(self):
        original=inputs();end=original.candles[5].close_time
        i=inputs(changed_catalog(available_until=end))
        candles=list(i.candles);candles[5]=replace(candles[5],high=D('4000'))
        s=replay(candles,i.config)
        trigger=next(e for e in s.events if e['type']=='PROTECTION_TRIGGER')
        self.assertEqual(trigger['at'],end)
        self.assertEqual(trigger['execution_time_model'],'BAR_CLOSE_RESOLUTION')
        self.assertEqual(s.balance.asset_quantity,0)
        self.assertEqual(len(s.fills),2)

    def test_foreign_events_and_unavailable_open_do_not_mutate(self):
        i=inputs();s=RiskSession(i.config)
        before=canonical(s.events)
        with self.assertRaises(ValidationError):s.on_open(replace(i.candles[0].opening(),symbol='BTCUSDT'))
        self.assertEqual(canonical(s.events),before)
        with self.assertRaises(ValidationError):s.on_open(replace(i.candles[0].opening(),at=i.config.window.start-timedelta(minutes=1)))
        self.assertEqual(canonical(s.events),before)
        s.on_open(i.candles[0].opening())
        before=canonical(s.events)
        with self.assertRaises(ValidationError):s.finish()
        self.assertEqual(s.status,'RUNNING')
        self.assertEqual(canonical(s.events),before)
        with self.assertRaises(ValidationError):s.on_close(replace(i.candles[0],symbol='BTCUSDT'))
        self.assertEqual(canonical(s.events),before)
        foreign=(*i.candles,replace(i.candles[-1],symbol='BTCUSDT',open_time=i.candles[-1].open_time+timedelta(minutes=1),close_time=i.candles[-1].close_time+timedelta(minutes=1)))
        with self.assertRaises(ValidationError):replay(foreign,i.config)
        with tempfile.TemporaryDirectory() as folder:
            raw=json.loads(DATA.read_text());raw['candles'][-1]['symbol']='BTCUSDT'
            path=Path(folder)/'foreign.json';path.write_text(json.dumps(raw))
            with self.assertRaises(ValidationError):load_inputs(path,CONFIG,CATALOG)

    def test_gap_preserves_position_reserve_and_prefix(self):
        i=inputs();s=replay((*i.candles[:5],i.candles[6]),i.config);p=report(s)
        self.assertEqual(s.status,'INTERRUPTED')
        self.assertEqual(p['exit_code'],1)
        self.assertEqual(p['coverage']['accepted_candles'],5)
        self.assertEqual(len(p['coverage']['gaps']),1)
        self.assertGreater(s.ledger.entries[-1].asset_reserved_after,0)
        self.assertEqual(p['analysis']['observed_until'],i.candles[4].close_time)
        truncated=replay(i.candles[:5],i.config)
        prefix=[e for e in truncated.events if e['type'] not in ('RELEASE','END')]
        self.assertEqual(canonical(s.events[:-1]),canonical(prefix))

    def test_incremental_isolation_duplicates_causality_and_rollback(self):
        children=load_matrix(MATRIX).children
        selected=[child for name,child in children if name.startswith('rsi')]
        sessions=[RiskSession(child.config) for child in selected]
        for index in range(7):
            for s,child in zip(sessions,selected):
                c=child.candles[index]
                s.on_open(c.opening());s.on_close(c)
                events=canonical(s.events)
                s.on_close(c);self.assertEqual(canonical(s.events),events)
        for s,child in zip(sessions,selected):
            s.finish();self.assertEqual(canonical(report(s)),canonical(report(replay(child.candles,child.config))))
        i=inputs();s=RiskSession(i.config);s.on_open(i.candles[0].opening())
        before=canonical(s.events)
        with patch.object(RiskSession,'_observe',side_effect=ValidationError('injected')):
            with self.assertRaises(ValidationError):s.on_close(i.candles[0])
        self.assertEqual(canonical(s.events),before)
        self.assertEqual(s.strategy.indicator.count,0)
        s=RiskSession(i.config)
        for c in i.candles[:4]:s.on_open(c.opening());s.on_close(c)
        prefix=canonical(s.events)
        for c in i.candles[4:]:
            c=replace(c,high=c.high+D(1))
            s.on_open(c.opening());s.on_close(c)
        self.assertEqual(canonical(s.events[:len(json.loads(prefix))]),prefix)

    def test_coverage_borders_duplicates_and_price_age(self):
        from replayquant.risk import RiskSnapshot, evaluate
        i = inputs()
        duplicate = replay((i.candles[0], *i.candles), i.config)
        p = report(duplicate)
        self.assertEqual(p['coverage']['duplicates'], 1)
        self.assertEqual(duplicate.strategy.indicator.count, 7)
        p = report(replay(i.candles[1:], i.config))
        self.assertEqual(p['coverage']['status'], 'PARTIAL')
        self.assertIn('DATA_START_MISSING', p['coverage']['reasons'])
        self.assertEqual(p['coverage']['missing_eligible_candles'], 1)
        at = i.candles[0].close_time
        snapshot = RiskSnapshot(D(1000), D(1000), D(0), D(2000), at, at + timedelta(seconds=60))
        self.assertTrue(evaluate(i.config, snapshot)['approved'])
        stale = replace(snapshot, evaluated_at=at + timedelta(seconds=61))
        self.assertEqual(evaluate(i.config, stale)['reason'], 'PRICE_STALE')
        with self.assertRaises(ValidationError):
            replace(snapshot, price_at=snapshot.evaluated_at + timedelta(seconds=1))

    def test_generic_formats_csv_and_escape(self):
        import csv
        from replayquant.exports import markdown_report
        i = inputs()
        metadata = manifest(i)
        s = replay(i.candles, i.config, metadata['run_id'])
        p = report(s)
        html = html_report(p)
        self.assertIn('USDT/ETH', html)
        self.assertNotIn('USDT/BTC', html)
        self.assertIn('BUY_HOLD_ASSET', html)
        self.assertIn('USDT/ETH', markdown_report(p))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'run'
            write_artifacts(target, metadata, s, p)
            for file in target.glob('*.csv'):
                with file.open() as stream:
                    rows = list(csv.DictReader(stream))
                self.assertTrue(all(row['base_asset'] == 'ETH' and row['symbol'] == 'ETHUSDT' for row in rows))
        changed = inputs(changed_catalog(rules_source='<script>alert(1)</script>'))
        output = html_report(report(replay(changed.candles, changed.config)))
        self.assertNotIn('<script>alert(1)</script>', output)
        self.assertIn('&lt;script&gt;', output)

    def test_cancel_and_hostile_decimal_context(self):
        i=inputs();s=RiskSession(i.config)
        for c in i.candles[:4]:s.on_open(c.opening());s.on_close(c)
        request=RiskRequest('cancel',i.candles[3].close_time,'CANCEL',s.pending)
        s.submit(request);before=canonical(s.events);s.submit(request)
        self.assertEqual(canonical(s.events),before)
        self.assertEqual(s.ledger.entries[-1].cash_reserved_after,0)
        expected=canonical(report(replay(i.candles,i.config)))
        with localcontext() as ctx:
            ctx.prec=2;ctx.traps[Inexact]=True
            flags=ctx.flags.copy()
            self.assertEqual(canonical(report(replay(i.candles,i.config))),expected)
            self.assertEqual(ctx.flags,flags)


class MatrixTests(unittest.TestCase):
    def test_permutation_identity_and_byte_reproduction(self):
        original=load_matrix(MATRIX);metadata,summary,runs=compare(original)
        value=json.loads(MATRIX.read_text())
        value['catalog']=str(CATALOG)
        for item in value['datasets']:item['path']=str((MATRIX.parent/item['path']).resolve())
        value['datasets'].reverse();value['strategies'].reverse()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'matrix.json';path.write_text(json.dumps(value))
            other_metadata,other,other_runs=compare(load_matrix(path))
            self.assertEqual(metadata['matrix_id'],other_metadata['matrix_id'])
            self.assertNotEqual(metadata['recipe_hash'],other_metadata['recipe_hash'])
            self.assertEqual(canonical(summary),canonical(other))
            for left,right in zip(runs,other_runs):self.assertEqual(canonical(left[2].events),canonical(right[2].events))
            a,b=Path(folder)/'a',Path(folder)/'b'
            write_comparison(a,metadata,summary,runs);write_comparison(b,metadata,summary,runs)
            files=[f for f in a.rglob('*') if f.is_file()]
            self.assertEqual(len(files),70)
            for f in files:self.assertEqual(f.read_bytes(),(b/f.relative_to(a)).read_bytes())
            with self.assertRaises(FileExistsError):write_comparison(a,metadata,summary,runs)

    def test_exact_ranking_ties_exclusions(self):
        _,summary,_=compare(load_matrix(MATRIX))
        rows=[deepcopy(r) for r in summary['rows'] if r['exit_code']==0]
        tied=deepcopy(rows[0]);tied['symbol']='SOLUSDT';rows.append(tied)
        rank(rows)
        self.assertEqual([r['rank'] for r in rows],[1,3,1])
        rows[0]['coverage']['status']='PARTIAL';rank(rows)
        self.assertIsNone(rows[0]['rank'])

    def test_invalid_matrix_and_failure_marker(self):
        value=json.loads(MATRIX.read_text())
        value['catalog']=str(CATALOG)
        for item in value['datasets']:item['path']=str((MATRIX.parent/item['path']).resolve())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'matrix.json'
            for key in ['strategies','datasets']:
                bad=deepcopy(value);bad[key].append(bad[key][0]);path.write_text(json.dumps(bad))
                with self.assertRaises(ValidationError):load_matrix(path)
            metadata,summary,runs=compare(load_matrix(MATRIX))
            with patch('replayquant.comparison.write_artifacts',side_effect=OSError('injected')):
                with self.assertRaises(OSError):write_comparison(Path(folder)/'broken',metadata,summary,runs)
            self.assertTrue((Path(folder)/'broken/INCOMPLETE').exists())
            self.assertFalse((Path(folder)/'broken/manifest.json').exists())

    def test_cli_relative_paths_other_cwd_and_formats(self):
        from replayquant.comparison import comparison_html, comparison_markdown
        _,summary,_=compare(load_matrix(MATRIX))
        self.assertIn('INDEPENDENT_CAPITAL_PER_RUN',comparison_html(summary))
        self.assertIn('ETHUSDT',comparison_markdown(summary))
        with tempfile.TemporaryDirectory() as folder:
            environment={**os.environ,'PYTHONPATH':str(ROOT)}
            result=subprocess.run([sys.executable,'-m','replayquant','comparar','--config',str(MATRIX),
                                   '--saida',str(Path(folder)/'result'),'--formato','json'],cwd=folder,
                                  env=environment,capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['matrix_id'],summary['matrix_id'])


if __name__ == '__main__':
    unittest.main()
