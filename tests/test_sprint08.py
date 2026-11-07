"""Ledger, curva, métricas, benchmarks e exportações da Sprint 08."""
from copy import deepcopy
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_UP, localcontext
from fractions import Fraction
from hashlib import sha256
from io import StringIO
from pathlib import Path
import csv
import json
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.data import load_inputs
from replayquant.engine import Session, SMASession, replay
from replayquant.models import Request
from replayquant.ledger import Ledger
from replayquant.analysis import analyze, project_curve
from replayquant.metrics import drawdowns, trade_statistics, ratio, percentage, metric
from replayquant.reporting import report, manifest, canonical, wire, write_artifacts, text_report
from replayquant.exports import markdown_report, analysis_files
from replayquant.html_report import html_report
from replayquant.validation import ValidationError

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/fixtures/sprint08-candles.json'
CONFIG=ROOT/'experiments/sprint08-manual.json'
SPEC=(ROOT/'docs/sprint08.md').read_text()
HEADERS={name: re.search(re.escape(name)+r':\n([^\n]+)',SPEC).group(1).split(',')
         for name in ('equity.csv','trades.csv','metrics.csv','benchmarks.csv')}
ARTIFACTS={'manifest.json','events.jsonl','report.json','ledger.jsonl','equity.csv','trades.csv','metrics.csv','benchmarks.csv','report.md'}


def cli(*args):
    return subprocess.run([sys.executable,'-m','replayquant',*map(str,args)],cwd=ROOT,capture_output=True,text=True)


def sma(expanded=False):
    suffix='-expandido' if expanded else ''
    return load_inputs(ROOT/f'data/fixtures/sprint07-candles{suffix}.json',ROOT/f'experiments/sprint07-sma{suffix}.json')


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.i=load_inputs(DATA,CONFIG)

    def session(self,candles=None,config=None):
        return replay(self.i.candles if candles is None else candles,self.i.config if config is None else config)

    def test_manual_exact_ledger_curve_and_metrics(self):
        s=self.session();r=report(s,analysis=True);a=r['analysis'];m=a['metrics']
        self.assertEqual(r['schema_version'],3)
        self.assertEqual(r['simulation_mode'],'MANUAL')
        self.assertEqual(len(a['ledger_entries']),3)
        self.assertEqual([e.cash_delta for e in a['ledger_entries']],[D('1000'),D('-100.1'),D('100.899')])
        self.assertEqual([e.asset_delta for e in a['ledger_entries']],[D('0'),D('.001'),D('-.001')])
        expected=['1000','1000','1000','1000','999.9','1000.9','1000.9','1000.799','1000.799']
        self.assertEqual([p['gross_equity'] for p in a['equity_curve']],list(map(D,expected)))
        for key,expected in [('realized_pnl','0.799'),('paid_fees','0.201'),('final_cash','1000.799'),
                             ('portfolio_return_pct','0.0799'),('max_drawdown_pct','0.010090918174'),
                             ('time_in_position_pct','33.333333333333'),('expectancy','.799')]:
            self.assertEqual(D(str(m[key]['value'])),D(expected),key)
        self.assertEqual((m['max_drawdown_pct']['numerator'],m['max_drawdown_pct']['denominator']),('101','10009'))
        self.assertEqual(m['max_drawdown_duration_seconds']['value'],60)
        self.assertEqual(m['time_in_position_seconds']['value'],60)
        self.assertEqual(m['observation_duration_seconds']['value'],180)
        self.assertEqual(a['closed_trades'][0]['return_pct']['value'],'0.798201798202')
        self.assertEqual(a['closed_trades'][0]['classification'],'WIN')
        self.assertEqual(a['max_drawdown_episode']['recovered'],False)
        self.assertEqual(a['max_drawdown_episode']['reason'],'NOT_RECOVERED')
        self.assertTrue(a['longest_drawdown_episode']['recovered'])

    def test_reconstruction_and_equity_identity_at_every_point(self):
        s=self.session();a=analyze(s)
        cash=asset=fees=D('0')
        for row in s.ledger.entries:
            cash+=row.cash_delta;asset+=row.asset_delta;fees+=row.fee
            self.assertEqual((cash,asset,fees),(row.cash_after,row.asset_after,row.fees_after))
        self.assertEqual((cash,asset,fees),(s.balance.cash,s.balance.btc,s.fees))
        for p in a['equity_curve']:
            self.assertEqual(p['gross_equity'],self.i.config.initial_cash+p['realized_pnl']+p['unrealized_pnl'])
            self.assertEqual(p['cash_available'],p['cash_total'])
            self.assertEqual(p['cash_reserved'],0)
        self.assertEqual(a['reconciliation']['status'],'PASSED')
        self.assertEqual(len(s.ledger.entries),3)  # Marcação não cria movimentos.

    def test_empty_schedule_preserves_valid_zeros_and_undefined_statistics(self):
        s=self.session(config=replace(self.i.config,orders=()))
        a=analyze(s);m=a['metrics']
        for key in ('realized_pnl','unrealized_pnl','paid_fees','closed_trade_count','time_in_position_seconds',
                    'portfolio_return_pct','max_drawdown_pct','max_drawdown_duration_seconds'):
            self.assertEqual(D(str(m[key]['value'])),0,key)
        for key in ('win_rate_pct','expectancy'):
            self.assertIsNone(m[key]['value']);self.assertEqual(m[key]['reason'],'NO_CLOSED_TRADES')
        self.assertEqual(len(s.ledger.entries),1)
        self.assertEqual(a['episode_reason'],'NO_DRAWDOWN')
        self.assertEqual(report(s,analysis=True)['exit_code'],0)
        self.assertEqual(a['benchmarks'][1]['metrics']['final_gross_equity']['value'],D('1008.991008991'))
        self.assertNotIn('None USDT',html_report(report(s,analysis=True)))

    def test_open_position_is_not_realized_or_forced_liquidated(self):
        s=self.session(self.i.candles[:2],replace(self.i.config,orders=self.i.config.orders[:1]))
        a=analyze(s);m=a['metrics']
        values={'final_cash':'899.9','final_asset_quantity':'.001','realized_pnl':'0','unrealized_pnl':'.9',
                'final_gross_equity':'1000.9','final_hypothetical_liquidation_equity':'1000.799','paid_fees':'.1'}
        for k,v in values.items():self.assertEqual(m[k]['value'],D(v),k)
        self.assertEqual(a['open_position']['cost_basis'],D('100.1'))
        self.assertEqual(a['open_position']['hypothetical_exit_fee'],D('.101'))
        self.assertEqual(m['time_in_position_pct']['value'],'50.000000000000')
        self.assertEqual(a['closed_trades'],[])
        self.assertEqual(len(s.fills),1)
        self.assertEqual(len(s.ledger.entries),2)
        self.assertNotIn('None USDT',html_report(report(s,analysis=True)))

    def test_sma_costs_are_visible_at_reference_open(self):
        i=sma();s=replay(i.candles,i.config);a=analyze(s)
        point=next(p for p in a['equity_curve'] if p['phase']=='FILL')
        self.assertEqual(point['gross_equity'],D('999.7999'))
        self.assertEqual(point['unrealized_pnl'],D('-.2001'))
        self.assertEqual(point['mark_price'],D('100000'))
        self.assertEqual(a['metrics']['paid_fees']['value'],D('.2'))
        self.assertEqual(a['metrics']['slippage_impact']['value'],D('.2'))
        self.assertEqual(a['metrics']['attributed_execution_costs']['value'],D('.4'))
        self.assertEqual(a['metrics']['realized_pnl']['value'],D('-.4'))
        self.assertEqual(report(s,analysis=True)['round_trip_result'],D('-.4'))

    def test_multiple_trades_realized_expectancy_and_exposure(self):
        i=sma(True);s=replay(i.candles,i.config);a=analyze(s);m=a['metrics']
        self.assertEqual([t['net_pnl'] for t in a['closed_trades']],list(map(D,['.73754871919','.77489849630','-.61089654715'])))
        self.assertEqual(m['realized_pnl']['value'],D('.90155066834'))
        self.assertEqual(m['expectancy']['value'],'0.300516889447')
        self.assertEqual(m['win_rate_pct']['value'],'66.666666666667')
        self.assertEqual(m['time_in_position_seconds']['value'],6120)
        self.assertEqual(m['time_in_position_pct']['value'],'42.500000000000')
        self.assertEqual(m['paid_fees']['value'],D('.60339361166'))
        self.assertEqual((m['win_count']['value'],m['loss_count']['value']), (2,1))
        self.assertIsNone(report(s,analysis=True)['round_trip_result'])
        self.assertIsNone(a['open_position'])

    def test_benchmarks_same_capital_dates_and_exact_downward_sizing(self):
        a=analyze(self.session());cash,bh=a['benchmarks']
        self.assertEqual(cash['metrics']['portfolio_return_pct']['value'],'0.000000000000')
        self.assertEqual(cash['metrics']['paid_fees']['value'],0)
        self.assertEqual(cash['metrics']['time_in_position_pct']['value'],'0.000000000000')
        self.assertEqual(bh['parameters']['quantity'],D('.009990009990'))
        self.assertEqual(bh['parameters']['cash_residual'],D('.000000001'))
        self.assertEqual(bh['metrics']['paid_fees']['value'],D('.999000999'))
        self.assertEqual(bh['metrics']['final_gross_equity']['value'],D('1008.991008991'))
        self.assertEqual(bh['metrics']['final_hypothetical_liquidation_equity']['value'],D('1007.98201798201'))
        self.assertEqual(bh['metrics']['time_in_position_pct']['value'],'100.000000000000')
        self.assertEqual(len(bh['ledger_entries']),2)
        for b in a['benchmarks']:
            self.assertEqual((b['observation_start'],b['observed_until']),(a['observation_start'],a['observed_until']))
            self.assertEqual(b['initial_cash'],D('1000'))
        i=sma();bh=analyze(replay(i.candles,i.config))['benchmarks'][1]
        ideal=Fraction(1000)/(Fraction(100000)*Fraction('1.001')*Fraction('1.001'))
        q=Fraction(bh['parameters']['quantity'])
        self.assertLessEqual(q,ideal);self.assertLess(ideal,q+Fraction(1,10**12))
        self.assertGreaterEqual(bh['parameters']['cash_residual'],0)

    def test_benchmark_below_quantum_is_unavailable_without_false_cash_equivalence(self):
        a=analyze(self.session(config=replace(self.i.config,initial_cash=D('.000000000001'),orders=())))
        bh=a['benchmarks'][1]
        self.assertEqual(bh['status'],'UNAVAILABLE')
        self.assertEqual(bh['reason'],'BENCHMARK_SIZE_BELOW_QUANTUM')
        self.assertEqual(bh['equity_curve'],[])
        self.assertEqual(bh['metrics'],{})
        self.assertEqual(len(bh['ledger_entries']),1)
        self.assertEqual(bh['ledger_entries'][0].fee,0)

    def test_ledger_preparation_is_immutable_idempotent_and_conflicts_are_atomic(self):
        s=self.session();ledger=s.ledger;fill=s.fills[0]
        self.assertIs(ledger.prepare(fill,D('100000'),999),ledger)
        with self.assertRaises(ValidationError):ledger.prepare(replace(fill,fee=D('1')),D('100000'),999)
        self.assertEqual(s.ledger,ledger)
        with self.assertRaises(FrozenInstanceError):ledger.entries[0].cash_delta=D('1')
        corrupted=replace(ledger,entries=(ledger.entries[0], replace(ledger.entries[1],cash_delta=D('-99')), *ledger.entries[2:]))
        with self.assertRaises(ValidationError):corrupted.reconcile()
        with self.assertRaises(ValidationError):replace(ledger.entries[0],ledger_seq=True)
        with self.assertRaises(ValidationError):ledger.prepare(fill,D('100000'),True)
        with self.assertRaises(ValidationError):Ledger.initial(True,'run')

    def test_failed_ledger_preparation_does_not_commit_cash_order_or_fill(self):
        s=Session(self.i.config,'api')
        c=self.i.candles
        s.on_open(c[0].opening());s.on_close(c[0]);s.submit(self.i.config.orders[0])
        before=(s.balance,s.pending,s.orders,s.fills,s.fees,s.ledger)
        with patch.object(Ledger,'prepare',side_effect=ValidationError('falha de preparação')):
            with self.assertRaises(ValidationError):s.on_open(c[1].opening())
        self.assertEqual((s.balance,s.pending,s.orders,s.fills,s.fees,s.ledger),before)
        self.assertFalse(any(e['type']=='FILLED' for e in s.events))

    def test_technical_interruption_is_not_reported_as_data_gap_in_benchmarks(self):
        i=sma();s=SMASession(i.config)
        for candle in i.candles[:4]:
            s.on_open(candle.opening());s.on_close(candle)
        with patch.object(Ledger,'prepare',side_effect=ValidationError('falha técnica')):
            with self.assertRaises(ValidationError):s.on_open(i.candles[4].opening())
        self.assertEqual(s.diagnostic['reason'],'INVALID_OPEN_OR_ARITHMETIC')
        a=analyze(s)
        self.assertTrue(all(b['reason']=='INVALID_OPEN_OR_ARITHMETIC' for b in a['benchmarks']))
        self.assertEqual(len(s.ledger.entries),1)

    def test_incremental_and_file_replay_use_same_ledger(self):
        s=Session(self.i.config,'api')
        for c in self.i.candles:
            s.on_open(c.opening());s.on_close(c)
            for request in self.i.config.orders:
                if request.at_close==c.close_time:s.submit(request)
        s.finish()
        reference=self.session()
        self.assertEqual(s.ledger,reference.ledger)
        self.assertEqual(analyze(s),analyze(reference))

    def test_prefix_and_future_ohlcv_do_not_change_past_ledger_or_valuations(self):
        i=sma();baseline=replay(i.candles,i.config)
        changed=list(i.candles)
        changed[4]=replace(changed[4],close=D('105000'),high=D('110000'),low=D('1'),volume=D('0'))
        newer=replay(changed,i.config)
        a,b=analyze(baseline),analyze(newer)
        limit=next(p['point_seq'] for p in a['equity_curve'] if p['phase']=='FILL')
        self.assertEqual(a['equity_curve'][:limit],b['equity_curve'][:limit])
        self.assertEqual(baseline.ledger.entries[:2],newer.ledger.entries[:2])
        prefix=replay(i.candles[:5],i.config)
        points=analyze(prefix)['equity_curve']
        self.assertEqual(a['equity_curve'][:len(points)],points)

    def test_gap_preserves_new_order_and_all_references_stop_at_prefix(self):
        i=sma()
        for removed in [4,5]:
            s=replay(i.candles[:removed]+i.candles[removed+1:],i.config)
            r=report(s,analysis=True);a=r['analysis']
            self.assertEqual((r['status'],r['exit_code'],a['scope']),('INTERRUPTED',1,'ACCEPTED_PREFIX'))
            self.assertEqual(a['observed_until'],i.candles[removed-1].close_time)
            for curve in [a['equity_curve']]+[b['equity_curve'] for b in a['benchmarks']]:
                self.assertTrue(all(p['at']<=a['observed_until'] for p in curve))
            if removed==4:
                self.assertEqual(s.orders[0].status,'NEW')
                self.assertEqual(len(s.ledger.entries),1)
                self.assertIsNotNone(s.pending)
            else:self.assertEqual(s.balance.btc,D('.001'))

    def test_rejected_and_last_orders_do_not_create_financial_movements(self):
        rejected=self.session(config=replace(self.i.config,initial_cash=D('100'),orders=self.i.config.orders[:1]))
        self.assertEqual(len(rejected.ledger.entries),1)
        self.assertEqual(report(rejected,analysis=True)['exit_code'],2)
        req=Request('last',self.i.candles[-1].close_time,'BUY')
        last=self.session(config=replace(self.i.config,orders=(req,)))
        self.assertEqual(last.orders[0].reason,'NO_FUTURE_OPEN')
        self.assertEqual(len(last.ledger.entries),1)
        self.assertEqual(analyze(last)['metrics']['closed_trade_count']['value'],0)

    def test_hostile_decimal_context_does_not_change_ledger_or_reporting(self):
        expected=report(self.session(),analysis=True)
        with localcontext() as ctx:
            ctx.prec=2;ctx.rounding=ROUND_UP;ctx.traps[Inexact]=True;ctx.flags[Inexact]=True
            before=ctx.copy()
            actual=report(self.session(),analysis=True)
            self.assertEqual(actual,expected)
            self.assertEqual(ctx.flags,before.flags);self.assertEqual(ctx.traps,before.traps);self.assertEqual(ctx.prec,2)


class MetricsTests(unittest.TestCase):
    def curve(self,values):
        start=datetime(2026,1,1,12,tzinfo=timezone.utc)
        return [dict(point_seq=i+1,at=start+timedelta(minutes=i),gross_equity=D(str(v))) for i,v in enumerate(values)]

    def test_manual_drawdown_recovery_and_open_episode(self):
        d=drawdowns(self.curve([1000,1100,990,1050,1100,1080]))
        self.assertEqual(d['max_drawdown_pct']['value'],'10.000000000000')
        self.assertEqual(d['max_drawdown_amount']['value'],D('110'))
        self.assertEqual(d['max_drawdown_duration_seconds']['value'],180)
        self.assertEqual(d['max_drawdown_episode']['peak_point_seq'],2)
        self.assertEqual(d['max_drawdown_episode']['trough_point_seq'],3)
        self.assertTrue(d['max_drawdown_episode']['recovered'])
        self.assertFalse(d['drawdown_episodes'][1]['recovered'])
        self.assertEqual(d['drawdown_episodes'][1]['duration_seconds'],60)

    def test_absolute_maximum_duration_and_percentage_are_independent(self):
        d=drawdowns(self.curve([1000,500,1000,2000,1400]))
        self.assertEqual(d['max_drawdown_pct']['value'],'50.000000000000')
        self.assertEqual(d['max_drawdown_amount']['value'],D('600'))
        self.assertEqual(d['max_drawdown_episode']['drawdown_amount'],D('500'))
        d=drawdowns(self.curve([1000,900,1000,980,970,960,950,1000]))
        self.assertNotEqual(d['max_drawdown_episode']['peak_at'],d['longest_drawdown_episode']['peak_at'])
        self.assertEqual(d['max_drawdown_duration_seconds']['value'],300)

    def test_equal_peaks_ties_and_same_timestamp(self):
        d=drawdowns(self.curve([1000,1000,900,1000,900]))
        self.assertEqual(d['max_drawdown_episode']['peak_point_seq'],2)
        self.assertEqual(d['max_drawdown_episode']['trough_point_seq'],3)
        curve=self.curve([1000,999])
        curve[1]['at']=curve[0]['at']
        d=drawdowns(curve)
        self.assertEqual(d['max_drawdown_duration_seconds']['value'],0)
        self.assertIsNone(d['max_drawdown_episode']['recovery_at'])
        d=drawdowns(self.curve([1000,1000,1000]))
        self.assertEqual(d['max_drawdown_pct']['value'],'0.000000000000')
        self.assertEqual(d['episode_reason'],'NO_DRAWDOWN')

    def test_expectancy_exact_signs_and_half_even_rounding(self):
        m=trade_statistics([D('2'),D('-1'),D('0')])
        self.assertEqual(m['expectancy']['value'],'0.333333333333')
        self.assertEqual(m['win_rate_pct']['value'],'33.333333333333')
        self.assertEqual(m['expectancy']['numerator'],'1');self.assertEqual(m['expectancy']['denominator'],'3')
        self.assertEqual(trade_statistics([D('.000000000000001')])['win_count']['value'],1)
        self.assertEqual(ratio(Fraction(5,2*10**12))['value'],'0.000000000002')
        self.assertEqual(ratio(Fraction(7,2*10**12))['value'],'0.000000000004')
        self.assertEqual(ratio(Fraction(-5,2*10**12))['value'],'-0.000000000002')
        self.assertEqual(percentage(0,0)['reason'],'ZERO_OBSERVATION_DURATION')

    def test_invalid_curves_types_and_boolean_counts(self):
        for curve in [[],self.curve([0]),self.curve([-1]),list(reversed(self.curve([1,2]))),[{}]]:
            with self.assertRaises(ValidationError):drawdowns(curve)
        for changes in [dict(point_seq=True),dict(gross_equity=1.0),dict(at=datetime(2026,1,1))]:
            curve=self.curve([1]);curve[0].update(changes)
            with self.assertRaises(ValidationError):drawdowns(curve)
        for values in [[True],[1.0],[D('NaN')]]:
            with self.assertRaises(ValidationError):trade_statistics(values)
        with self.assertRaises(ValidationError):metric(True,'SECONDS')
        with self.assertRaises(ValidationError):percentage(True,1)


class ExportTests(unittest.TestCase):
    def setUp(self):self.i=load_inputs(DATA,CONFIG)

    def test_analysis_flag_identity_and_legacy_schemas(self):
        legacy=manifest(self.i);new=manifest(self.i,analysis=True)
        self.assertNotEqual(new['run_id'],legacy['run_id'])
        identity={k:new[k] for k in ('data_hash','config_hash','code_hash','python_version','analysis_policy')}
        self.assertEqual(new['run_id'],sha256(canonical(identity)).hexdigest())
        self.assertEqual(new['schema_version'],3)
        s=replay(self.i.candles,self.i.config)
        self.assertEqual(report(s)['schema_version'],1)
        i=sma();self.assertEqual(report(replay(i.candles,i.config))['schema_version'],2)
        for value in [1,'true',None]:
            with self.assertRaises(ValidationError):manifest(self.i,analysis=value)
            with self.assertRaises(ValidationError):report(s,analysis=value)

    def test_nine_reproducible_artifacts_and_csv_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirs=[Path(tmp)/'a',Path(tmp)/'b']
            for target in dirs:
                p=cli('executar','--dados',DATA,'--config',CONFIG,'--analise','--saida',target,'--formato','json')
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertEqual({p.name for p in target.iterdir()},ARTIFACTS)
                self.assertEqual(json.loads(p.stdout),json.loads((target/'report.json').read_text()))
            for name in ARTIFACTS:self.assertEqual((dirs[0]/name).read_bytes(),(dirs[1]/name).read_bytes(),name)
            restored=json.loads((dirs[0]/'report.json').read_text())
            original=report(replay(self.i.candles,self.i.config,restored['run_id']),analysis=True)
            self.assertEqual(sha256(html_report(restored).encode()).hexdigest(),sha256(html_report(original).encode()).hexdigest())
            for name, content in analysis_files(restored).items():
                self.assertEqual(content,(dirs[0]/name).read_text(),name)
            for name,headers in HEADERS.items():
                raw=(dirs[0]/name).read_text()
                self.assertNotIn('\r',raw)
                reader=csv.DictReader(StringIO(raw))
                self.assertEqual(reader.fieldnames,headers)
                rows=list(reader)
                self.assertTrue(all(row['schema_version']=='3' for row in rows))
            trades=list(csv.DictReader(StringIO((dirs[0]/'trades.csv').read_text())))
            self.assertEqual(D(trades[0]['net_pnl']),D('.799'))
            metrics={row['metric']:row for row in csv.DictReader(StringIO((dirs[0]/'metrics.csv').read_text()))}
            self.assertEqual(metrics['max_drawdown_pct']['numerator'],'101')
            ledger=[json.loads(line) for line in (dirs[0]/'ledger.jsonl').read_text().splitlines()]
            self.assertEqual(len(ledger),6)  # 3 estratégia, 1 caixa, 2 comprar/manter.
            self.assertTrue(all(e['schema_version']==3 for e in ledger))
            events=[json.loads(line) for line in (dirs[0]/'events.jsonl').read_text().splitlines()]
            self.assertTrue(all(e['schema_version']==3 for e in events))
            before={p.name:p.read_bytes() for p in dirs[0].iterdir()}
            refused=cli('executar','--dados',DATA,'--config',CONFIG,'--analise','--saida',dirs[0])
            self.assertEqual(refused.returncode,1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in dirs[0].iterdir()})

    def test_empty_csv_and_null_reason_without_fake_win_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=json.loads(CONFIG.read_text());config['orders']=[]
            cfg=root/'config.json';cfg.write_text(json.dumps(config))
            p=cli('executar','--dados',DATA,'--config',cfg,'--analise','--saida',root/'out')
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual((root/'out/trades.csv').read_text(),','.join(HEADERS['trades.csv'])+'\n')
            rows={r['metric']:r for r in csv.DictReader(StringIO((root/'out/metrics.csv').read_text()))}
            self.assertEqual(rows['win_rate_pct']['value'],'')
            self.assertEqual(rows['win_rate_pct']['reason'],'NO_CLOSED_TRADES')

    def test_demo_formats_and_markdown_requires_analysis(self):
        for mode in [[],['--estrategia','sma']]:
            for fmt in ['texto','json','markdown','html']:
                p=cli('demonstrar',*mode,'--analise','--formato',fmt)
                self.assertEqual(p.returncode,0,p.stderr)
                if fmt=='json':self.assertEqual(json.loads(p.stdout)['schema_version'],3)
                else:self.assertIn('Patrimônio',p.stdout)
        self.assertEqual(cli('demonstrar','--formato','markdown').returncode,2)
        self.assertEqual(cli('demonstrar','--analise','true').returncode,2)

    def test_gap_and_rejections_keep_analysis_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            i=sma();raw=json.loads((ROOT/'data/fixtures/sprint07-candles.json').read_text())
            del raw['candles'][4]
            data=root/'gap.json';data.write_text(json.dumps(raw))
            p=cli('executar','--dados',data,'--config',ROOT/'experiments/sprint07-sma.json','--analise','--saida',root/'gap','--formato','json')
            self.assertEqual(p.returncode,1,p.stderr)
            self.assertEqual({p.name for p in (root/'gap').iterdir()},ARTIFACTS)
            r=json.loads(p.stdout)
            self.assertEqual(r['orders'][0]['status'],'NEW')
            self.assertEqual(r['analysis']['scope'],'ACCEPTED_PREFIX')
            c=json.loads(CONFIG.read_text());c['initial_cash']='100';c['orders']=c['orders'][:1]
            cfg=root/'reject.json';cfg.write_text(json.dumps(c))
            p=cli('executar','--dados',DATA,'--config',cfg,'--analise','--saida',root/'reject','--formato','json')
            self.assertEqual(p.returncode,2)
            self.assertEqual(len(json.loads(p.stdout)['analysis']['ledger_entries']),1)
            invalid=root/'invalid.json';invalid.write_text('{}')
            p=cli('executar','--dados',invalid,'--config',CONFIG,'--analise','--saida',root/'absent')
            self.assertEqual(p.returncode,1);self.assertFalse((root/'absent').exists())

    def test_serialization_failure_and_write_failure_are_not_success(self):
        s=replay(self.i.candles,self.i.config);m=manifest(self.i,analysis=True);r=report(s,analysis=True)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out'
            with patch('pathlib.Path.open',side_effect=OSError('disco')):
                with self.assertRaises(OSError):write_artifacts(target,m,s,r)
            self.assertTrue(target.exists())
        corrupted=replace(s.ledger,entries=(s.ledger.entries[0], replace(s.ledger.entries[1],cash_delta=D('-99')), *s.ledger.entries[2:]))
        with patch.object(type(s),'ledger',new_callable=unittest.mock.PropertyMock,return_value=corrupted):
            with self.assertRaises(ValidationError):report(s,analysis=True)

    def test_html_preserves_same_timestamp_points_and_escapes_payload(self):
        s=replay(self.i.candles,self.i.config);r=report(s,analysis=True)
        a=r['analysis']
        self.assertNotEqual(a['equity_curve'][3]['gross_equity'],a['equity_curve'][4]['gross_equity'])
        self.assertEqual(a['equity_curve'][3]['at'],a['equity_curve'][4]['at'])
        h=html_report(r)
        self.assertIn('Eixo horizontal por índice de evento',h)
        self.assertEqual(h.count('id="lightweight-charts-library"'),1)
        self.assertEqual(h.count('class="equity-chart"'),3)
        r=wire(r);r['analysis']['closed_trades'][0]['trade_id']='<script>alert(1)</script>'
        r['analysis']['equity_curve'][0]['at']='</script><script>alert(1)</script>'
        h=html_report(r)
        self.assertNotIn('<script>alert(1)',h)
        self.assertIn(r'\u003c/script\u003e',h)
        self.assertIn('&lt;script&gt;',h)

    def test_offline_and_external_context_output_is_reproducible(self):
        s=replay(self.i.candles,self.i.config);expected=report(s,analysis=True)
        with patch.object(socket,'socket',side_effect=AssertionError('rede')):
            with localcontext() as ctx:
                ctx.prec=2;ctx.traps[Inexact]=True;ctx.flags[Inexact]=True
                m=manifest(self.i,analysis=True);r=report(s,analysis=True)
                self.assertEqual(r,expected)
                self.assertIn('Patrimônio',markdown_report(r))
                self.assertIn('Patrimônio',text_report(r))
                self.assertEqual(len(m['run_id']),64)


if __name__=='__main__':unittest.main()
