"""Contratos causais/financeiros da SMA, incluindo API incremental e CLI."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, Inexact, ROUND_UP, localcontext
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.data import load_inputs, parse_candles, parse_config
from replayquant.engine import SMASession, replay
from replayquant.html_report import html_report
from replayquant.models import SMAParameters, Request
from replayquant.reporting import manifest, report, text_report, wire
from replayquant.strategies import SMACross
from replayquant.validation import ValidationError

D = Decimal
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/fixtures/sprint07-candles.json'
CONFIG = ROOT / 'experiments/sprint07-sma.json'


def inputs():
    return load_inputs(DATA, CONFIG)


def sequence(values):
    template = inputs().candles[0]
    return tuple(replace(template, open_time=template.open_time + timedelta(minutes=i),
                         close_time=template.close_time + timedelta(minutes=i),
                         open=D(str(v)), high=D(str(v)), low=D(str(v)), close=D(str(v)))
                 for i, v in enumerate(values))


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'replayquant', *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True)


class SMATests(unittest.TestCase):
    def setUp(self):
        self.i = inputs()
        self.c = self.i.candles
        self.config = self.i.config

    def run_replay(self, candles=None, config=None):
        return replay(self.c if candles is None else candles,
                      self.config if config is None else config)

    def progressive(self, count):
        s = SMASession(self.config)
        for c in self.c[:count]:
            s.on_open(c.opening())
            s.on_close(c)
        return s

    def test_required_fixture_exact_and_traceable(self):
        s = self.run_replay()
        r = report(s)
        self.assertEqual((s.balance.cash, s.balance.btc, s.fees), (D('999.6'), D('0'), D('.2')))
        self.assertEqual(r['round_trip_result'], D('-.4'))
        self.assertEqual([f.price for f in s.fills], [D('100100'), D('99900')])
        self.assertEqual([f.fee for f in s.fills], [D('.1001'), D('.0999')])
        self.assertEqual([len(r[k]) for k in ['evaluations','signals','decisions','intentions','orders','fills']],
                         [8,2,2,2,2,2])
        self.assertEqual(r['evaluations'][5]['comparison'], 0)
        self.assertIsNone(r['evaluations'][5]['side'])
        self.assertEqual(r['evaluations'][6]['previous_comparison'], 0)
        for decision, order, fill in zip(r['decisions'], s.orders, s.fills):
            self.assertTrue(decision['approved'])
            self.assertEqual(decision['order_id'], order.request.id)
            self.assertEqual(fill.order_id, order.request.id)
            self.assertIsNotNone(decision['intent_id'])
        self.assertEqual(r['status'], 'COMPLETED')
        self.assertEqual(r['exit_code'], 0)

    def test_warmup_minimum_windows_and_constant_prices(self):
        for windows in [(1,2),(2,3)]:
            config = replace(self.config, strategy=SMAParameters('SMA_CROSS', *windows))
            s = self.run_replay(sequence([3,3,3,3,3]), config)
            ev = report(s)['evaluations']
            self.assertTrue(all(e['reason'] == 'WARMUP' for e in ev[:windows[1]]))
            self.assertEqual(ev[windows[1]]['reason'], 'NO_CROSS')
            self.assertEqual(s.orders, ())
            self.assertEqual(report(s)['exit_code'], 0)
        self.assertEqual(report(self.run_replay(self.c[:1]))['exit_code'], 0)

    def test_equalities_and_persistence_both_directions(self):
        strategy = SMACross(SMAParameters('SMA_CROSS',1,2))
        ev = [strategy.on_close(c) for c in sequence([2,2,3,4,4,3,2,2,3])]
        self.assertEqual([e['side'] for e in ev],
                         [None,None,'BUY',None,None,'SELL',None,None,'BUY'])
        # A primeira média acima não é uma entrada.
        strategy = SMACross(SMAParameters('SMA_CROSS',1,2))
        self.assertEqual([strategy.on_close(c)['side'] for c in sequence([1,2,3])], [None]*3)

    def test_cross_below_display_precision_with_hostile_context(self):
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_UP
            ctx.traps[Inexact] = True
            ctx.flags[Inexact] = True
            snapshot = ctx.copy()
            strategy = SMACross(SMAParameters('SMA_CROSS',1,2))
            ev = [strategy.on_close(c) for c in sequence(['1','.000000000001','.000000000002'])]
            self.assertEqual(ev[-1]['side'], 'BUY')
            self.assertEqual(ev[-1]['long'], {'numerator':'3','denominator':'2000000000000'})
            self.assertEqual(ctx.prec, snapshot.prec)
            self.assertEqual(ctx.flags, snapshot.flags)
            self.assertEqual(ctx.traps, snapshot.traps)

    def test_same_timestamp_strict_event_sequence_and_open_payload(self):
        s = self.run_replay()
        self.assertEqual([e['seq'] for e in s.events], list(range(1,len(s.events)+1)))
        order = s.orders[0]
        filled = next(e for e in s.events if e['type']=='FILLED')
        self.assertEqual(filled['at'], order.request.at_close)
        self.assertGreater(filled['seq'], order.submitted_seq)
        for event in s.events:
            if event['type'] == 'OPEN':
                self.assertEqual(set(event), {'schema_version','run_id','seq','at','type','source','symbol','interval','price'})
        s = self.progressive(4)
        self.assertEqual(s.balance.cash, D('1000'))
        self.assertEqual(s.fills, ())
        with self.assertRaises(ValidationError):
            s.on_open(self.c[4])
        self.assertEqual(s.balance.cash, D('1000'))

    def test_prefix_causal_and_filling_candle_ohlcv_not_used_early(self):
        baseline = self.run_replay()
        changed = list(self.c)
        changed[4] = replace(changed[4], close=D('105000'), high=D('110000'), low=D('1'), volume=D('0'))
        changed[6] = replace(changed[6], close=D('90000'), low=D('90000'))
        newer = self.run_replay(changed)
        self.assertEqual(baseline.fills[0], newer.fills[0])
        stop = next(e['seq'] for e in baseline.events if e['type']=='FILLED')
        self.assertEqual(baseline.events[:stop], newer.events[:stop])
        prefix = self.run_replay(self.c[:5])
        events = [e for e in prefix.events if e['type'] != 'END']
        self.assertEqual(baseline.events[:len(events)], events)
        self.assertEqual(baseline.fills[0], prefix.fills[0])

    def test_last_order_and_open_position(self):
        s = self.run_replay(self.c[:4])
        self.assertEqual((s.orders[0].status,s.orders[0].reason), ('UNEXECUTED','NO_FUTURE_OPEN'))
        self.assertEqual((s.balance.cash,s.balance.btc,s.fees),(D('1000'),D('0'),D('0')))
        self.assertEqual(report(s)['exit_code'],2)
        self.assertIsNone(report(s)['round_trip_result'])
        s = self.run_replay(self.c[:5])
        self.assertEqual((s.balance.cash,s.balance.btc),(D('899.7999'),D('.001')))
        self.assertIsNone(report(s)['round_trip_result'])
        self.assertEqual(report(s)['exit_code'],0)

    def test_gaps_preserve_pending_or_position_and_cannot_resume(self):
        for removed, cash, btc, pending in [(4,'1000','0',True),(5,'899.7999','.001',False)]:
            s = self.run_replay(self.c[:removed]+self.c[removed+1:])
            self.assertEqual(s.status,'INTERRUPTED')
            self.assertEqual((s.balance.cash,s.balance.btc),(D(cash),D(btc)))
            self.assertEqual(s.pending is not None,pending)
            self.assertEqual(s.strategy.count,removed)
            self.assertEqual(s.diagnostic['reason'],'DATA_GAP')
            self.assertEqual(s.diagnostic['expected'],self.c[removed-1].close_time)
            self.assertEqual(s.diagnostic['found'],self.c[removed+1].open_time)
            self.assertFalse(any(e['type'] in ('OPEN','CLOSE') and e['at'] >= self.c[removed+1].open_time for e in s.events))
            if pending:
                self.assertEqual(s.orders[0].status,'NEW')
                self.assertEqual(s.fees,0)
            self.assertEqual(report(s)['exit_code'],1)
            self.assertEqual(report(s)['round_trip_reason'],'REPLAY_INTERRUPTED')
            self.assertIsNone(report(s)['round_trip_result'])
            with self.assertRaises(ValidationError): s.finish()
            with self.assertRaises(ValidationError): s.on_open(self.c[removed].opening())
        self.assertEqual(self.run_replay().status,'COMPLETED')

    def test_submission_includes_fee_and_slippage_and_no_retry(self):
        s = self.run_replay(self.c[:6],replace(self.config,initial_cash=D('102.102')))
        # close de 102000 exige 102.204102; taxa e slippage estão na estimativa.
        self.assertEqual(s.orders,())
        self.assertEqual(report(s)['decisions'][0]['reason'],'INSUFFICIENT_CASH')
        self.assertEqual(s.balance.cash,D('102.102'))
        self.assertEqual(len(report(s)['signals']),1)
        self.assertEqual(report(s)['exit_code'],2)
        self.assertEqual(s.fees,0)

    def test_next_open_rejects_without_retry_or_mutation(self):
        cs = list(self.c[:6])
        cs[4] = replace(cs[4],open=D('200000'),high=D('200000'))
        s = self.run_replay(cs,replace(self.config,initial_cash=D('103')))
        self.assertEqual(len(s.orders),1)
        self.assertEqual(s.orders[0].reason,'INSUFFICIENT_CASH')
        self.assertEqual((s.balance.cash,s.balance.btc,s.fees),(D('103'),D('0'),D('0')))
        self.assertIsNone(s.pending)
        self.assertEqual(s.fills,())
        self.assertEqual(len(report(s)['signals']),1)

    def test_new_attempt_requires_a_new_cross(self):
        cs = list(sequence([3,2,1,4,5,6,2,1,5,6]))
        # 2/3 cruza para cima em k=4, mas a abertura k=5 invalida o caixa.
        cs[4] = replace(cs[4], open=D('1000000'), high=D('1000000'))
        s = self.run_replay(cs, replace(self.config, initial_cash=D('10')))
        decisions = report(s)['decisions']
        buys = [e for e in report(s)['signals'] if e['side'] == 'BUY']
        self.assertEqual([e['at'] for e in buys], [cs[3].close_time, cs[8].close_time])
        self.assertEqual(len(s.orders), 2)
        self.assertEqual(s.orders[0].status, 'REJECTED')
        self.assertEqual(s.orders[1].status, 'FILLED')
        self.assertEqual(decisions[1]['reason'], 'INSUFFICIENT_ASSET')
        self.assertEqual(s.fills[0].at, cs[9].open_time)

    def test_incremental_policy_and_intent_duplicate_conflicts(self):
        s = self.progressive(1)
        blocked = s.handle_signal('sell-empty','SELL',self.c[0].close_time)
        self.assertEqual(blocked['reason'],'INSUFFICIENT_ASSET')
        approved = s.handle_signal('buy','BUY',self.c[0].close_time)
        snapshot = (s.events,s.pending,s.balance)
        self.assertEqual(s.handle_signal('buy','BUY',self.c[0].close_time),approved)
        self.assertEqual((s.events,s.pending,s.balance),snapshot)
        with self.assertRaises(ValidationError):
            s.handle_signal('buy','SELL',self.c[0].close_time)
        self.assertEqual((s.events,s.pending,s.balance),snapshot)
        self.assertEqual(s.handle_signal('second','SELL',self.c[0].close_time)['reason'],'ORDER_PENDING')
        self.assertEqual(s.pending, snapshot[1])
        s.on_open(self.c[1].opening())
        s.on_close(self.c[1])
        self.assertEqual(s.handle_signal('buy-open','BUY',self.c[1].close_time)['reason'],'POSITION_OPEN')
        self.assertEqual(s.balance.btc,D('.001'))
        with self.assertRaises(ValidationError):
            s.submit(Request('external',self.c[1].close_time,'BUY'))

    def test_slippage_zero_and_prices_outside_ohlc(self):
        s = self.run_replay(config=replace(self.config,slippage_rate=D('0')))
        self.assertEqual([f.price for f in s.fills],[D('100000')]*2)
        self.assertEqual((s.balance.cash,s.fees),(D('999.8'),D('.2')))
        cs = list(self.c)
        # Uma abertura não conhece limites do candle; o preenchimento pode ultrapassá-los.
        cs[4] = replace(cs[4],high=D('100000'),close=D('100000'))
        s = self.run_replay(cs)
        self.assertGreater(s.fills[0].price,cs[4].high)
        self.assertEqual(s.fills[0].fee,D('.1001'))
        cs = list(self.c)
        cs[7] = replace(cs[7], high=D('100000'), low=D('100000'), close=D('100000'))
        s = self.run_replay(cs)
        self.assertLess(s.fills[1].price, cs[7].low)

    def test_decimal_context_and_derived_price_not_input_limited(self):
        expected = report(self.run_replay())
        with localcontext() as ctx:
            ctx.prec=2
            ctx.rounding=ROUND_UP
            ctx.traps[Inexact]=True
            ctx.flags[Inexact]=True
            before=ctx.copy()
            self.assertEqual(report(self.run_replay()),expected)
            self.assertEqual(ctx.flags,before.flags)
            self.assertEqual(ctx.traps,before.traps)
            self.assertEqual(ctx.prec,2)
        s = SMASession(replace(self.config,initial_cash=D('2000')))
        for candle in self.c[:4]:
            s.on_open(candle.opening())
            s.on_close(candle)
        opening=replace(self.c[4].opening(),price=D('999999.999999999999'))
        s.on_open(opening)
        # preço efetivo tem mais de 18 dígitos, mas continua válido como valor derivado.
        self.assertEqual(s.fills[0].price,D('1000999.999999999998999'))

    def test_arithmetic_failure_does_not_mutate_financial_state(self):
        s = self.progressive(4)
        snapshot=(s.balance,s.pending,s.orders,s.fees,s.fills)
        with patch('replayquant.engine.after_fill',side_effect=ValidationError('inexata')):
            with self.assertRaises(ValidationError): s.on_open(self.c[4].opening())
        self.assertEqual((s.balance,s.pending,s.orders,s.fees,s.fills),snapshot)
        self.assertEqual(s.status,'INTERRUPTED')
        self.assertFalse(any(e['type']=='FILLED' for e in s.events))

    def test_real_inexact_balance_change_is_atomic(self):
        config=replace(self.config,initial_cash=D('999999999999999999'),quantity=D('.000000000001'),
                       fee_rate=D('.000000000001'),slippage_rate=D('.000000000001'))
        s=SMASession(config)
        for c in self.c[:4]:
            s.on_open(c.opening()); s.on_close(c)
        snapshot=(s.balance,s.orders,s.pending,s.fees,s.fills)
        # 18 dígitos de caixa menos desembolso com 36 casas não cabe na precisão 40.
        with self.assertRaises(ValidationError): s.on_open(self.c[4].opening())
        self.assertEqual((s.balance,s.orders,s.pending,s.fees,s.fills),snapshot)
        self.assertEqual(s.status,'INTERRUPTED')

    def test_duplicate_candle_open_evaluation_and_fill_are_inert(self):
        s = self.progressive(4)
        snapshot=(s.events,s.balance,s.strategy.count,s.pending)
        s.on_close(self.c[3]); s.on_open(self.c[3].opening())
        self.assertEqual((s.events,s.balance,s.strategy.count,s.pending),snapshot)
        s.on_open(self.c[4].opening())
        snapshot=(s.events,s.balance,s.fees)
        s.apply_fill(s.fills[0])
        self.assertEqual((s.events,s.balance,s.fees),snapshot)
        with self.assertRaises(ValidationError): s.apply_fill(replace(s.fills[0],fee=D('1')))
        self.assertEqual((s.events,s.balance,s.fees),snapshot)
        duplicate=self.c[:4]+(self.c[3],)+self.c[4:]
        replayed=self.run_replay(duplicate)
        self.assertEqual(replayed.fills,self.run_replay().fills)
        self.assertEqual(len(report(replayed)['evaluations']),8)

    def test_future_duplicate_diagnostic_does_not_shift_past_evaluations(self):
        baseline = self.run_replay()
        newer = self.run_replay(self.c + (self.c[0],))
        self.assertEqual(report(baseline)['evaluations'], report(newer)['evaluations'])
        self.assertEqual(report(baseline)['decisions'], report(newer)['decisions'])
        diagnostic = next(e for e in newer.events if e['type'] == 'DIAGNOSTIC')
        self.assertEqual(diagnostic['at'], self.c[-1].close_time)
        self.assertGreater(diagnostic['seq'], report(newer)['evaluations'][-1]['seq'])

    def test_incremental_conflicts_and_order_preserve_history(self):
        s=self.progressive(4)
        before=(s.balance,s.orders,s.pending,s.strategy.count,s.fills)
        with self.assertRaises(ValidationError): s.on_close(replace(self.c[3],volume=D('2')))
        self.assertEqual((s.balance,s.orders,s.pending,s.strategy.count,s.fills),before)
        self.assertEqual(s.status,'INTERRUPTED')
        self.assertEqual(s.events[-1]['reason'],'CONFLICTING_CANDLE')
        s=self.progressive(4)
        before=(s.balance,s.pending,s.orders,s.strategy.count)
        with self.assertRaises(ValidationError): s.on_open(replace(self.c[3].opening(),price=D('1')))
        self.assertEqual((s.balance,s.pending,s.orders,s.strategy.count),before)
        s=self.progressive(4)
        with self.assertRaises(ValidationError):
            s.on_open(replace(self.c[0].opening(),at=self.c[0].open_time-timedelta(minutes=1)))
        self.assertEqual(s.balance.cash,D('1000'))

    def test_api_conflicting_order_and_early_fill_are_inert(self):
        from replayquant.execution import make_sma_fill
        s = self.progressive(4)
        order = s.orders[0]
        snapshot = (s.balance, s.events, s.pending, s.orders, s.fills)
        self.assertEqual(s.submit(order.request), order)
        with self.assertRaises(ValidationError):
            s.submit(replace(order.request, side='SELL'))
        fill = make_sma_fill(order.request, self.c[4].opening(), self.config.quantity,
                             self.config.fee_rate, self.config.slippage_rate)
        with self.assertRaises(ValidationError): s.apply_fill(fill)
        self.assertEqual((s.balance, s.events, s.pending, s.orders, s.fills), snapshot)

    def test_indicator_failure_preserves_accepted_history(self):
        s = self.progressive(3)
        s.on_open(self.c[3].opening())
        before = (s.balance, s.orders, s.pending, s.strategy.count, s.fees)
        with patch.object(SMACross, 'on_close', side_effect=ValidationError('falha indicador')):
            with self.assertRaises(ValidationError): s.on_close(self.c[3])
        self.assertEqual((s.balance, s.orders, s.pending, s.strategy.count, s.fees), before)
        self.assertEqual(s.status, 'INTERRUPTED')
        self.assertEqual(sum(e['type'] == 'EVALUATION' for e in s.events), 3)

    def test_unexpected_technical_failure_propagates(self):
        with patch('replayquant.engine.after_fill',side_effect=RuntimeError('falha técnica')):
            with self.assertRaises(RuntimeError): self.run_replay()


class SMAValidationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text())
        self.data = json.loads(DATA.read_text())

    def parse(self, config):
        return parse_config(json.dumps(config).encode())

    def test_invalid_windows_in_json_and_python(self):
        for short,long in [(0,3),(-1,3),(3,3),(4,3),(True,3),(1,False),(1.0,3),('1',3),(1,3.0)]:
            with self.subTest(short=short,long=long):
                c=deepcopy(self.config)
                c['strategy'].update(short_window=short,long_window=long)
                with self.assertRaises(ValidationError): self.parse(c)
                with self.assertRaises(ValidationError): SMAParameters('SMA_CROSS',short,long)
        with self.assertRaises(ValidationError): SMAParameters('EMA',1,2)

    def test_strict_versions_fields_and_rates(self):
        for key,value in [('schema_version',True),('schema_version',2.0),('schema_version','2'),
                          ('schema_version',3),('orders',[]),('strategy',{}),('fee_rate','1'),
                          ('slippage_rate','1'),('slippage_rate','-0.001'),('fee_rate',0.1),
                          ('slippage_rate','NaN'),('quantity',True),('initial_cash','0')]:
            with self.subTest(key=key,value=value):
                c=deepcopy(self.config);c[key]=value
                with self.assertRaises(ValidationError): self.parse(c)
        with self.assertRaises(ValidationError): parse_config(b'{"schema_version":2,"schema_version":2}')
        c=deepcopy(self.config);c['strategy']['extra']=0
        with self.assertRaises(ValidationError): self.parse(c)
        for key,val in [('slippage_rate',D('1')),('fee_rate',D('-1')),('quantity',True),('strategy',{})]:
            with self.assertRaises(ValidationError): replace(inputs().config,**{key:val})

    def test_invalid_series_before_replay_and_gaps_only_sma(self):
        c=inputs().candles
        for candles in [(c[1],c[0]), c+(replace(c[0],volume=D('2')), )]:
            with self.assertRaises(ValidationError): replay(candles,inputs().config)
        with self.assertRaises(ValidationError): parse_candles(json.dumps(dict(schema_version=1,candles=self.data['candles'][::2])).encode())
        for field,value in [('is_closed',False),('volume','-1'),('close','NaN'),('open_time','2026-01-01T12:00:00'),('low','200000')]:
            d=deepcopy(self.data);d['candles'][0][field]=value
            with self.assertRaises(ValidationError): parse_candles(json.dumps(d).encode(),contiguous=False)
        d=deepcopy(self.data)
        for candle in d['candles']:
            for key in ['open_time','close_time']:
                original=candle[key]
                hour=int(original[11:13])-3
                candle[key]=original[:11]+f'{hour:02}'+original[13:-6]+'-03:00'
        parsed,_=parse_candles(json.dumps(d).encode(),contiguous=False)
        self.assertEqual(parsed,c)


class SMACliTests(unittest.TestCase):
    def test_demo_formats_and_escaping(self):
        for fmt in ['texto','json','html']:
            p=cli('demonstrar','--estrategia','sma','--formato',fmt)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(p.stderr,'')
            if fmt=='json':
                r=json.loads(p.stdout)
                self.assertEqual(D(r['final_balance']['cash']),D('999.6'))
            else:
                for label in ['Avaliações','Sinais','Decisões','Intenções']:
                    self.assertIn(label,p.stdout)
                self.assertIn('USDT',p.stdout)
                if fmt=='html':
                    self.assertTrue(p.stdout.startswith('<!doctype html>'))
                    self.assertIn('@media print',p.stdout)
                    self.assertNotIn('Ordens manuais',p.stdout)
        r=report(replay(inputs().candles,inputs().config))
        r['signals'][0]['signal_id']='<script>alert(1)</script>'
        h=html_report(r)
        self.assertNotIn('<script>',h)
        self.assertIn('&lt;script&gt;',h)
        self.assertNotIn('src="http',h)

    def test_artifacts_reproducibility_manifest_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            for target in [a,b]:
                p=cli('executar','--dados',DATA,'--config',CONFIG,'--saida',target,'--formato','json')
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertEqual(p.stderr,'')
                self.assertEqual(json.loads(p.stdout)['schema_version'],2)
            for name in ['manifest.json','events.jsonl','report.json']:
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            metadata=json.loads((a/'manifest.json').read_text())
            self.assertEqual(metadata,wire(manifest(inputs())))
            self.assertEqual(metadata['warmup_candles'],4)
            self.assertEqual(metadata['gap_policy'],'INTERRUPT_PRESERVE_STATE')
            self.assertEqual(metadata['strategy']['name'],'SMA_CROSS')
            events=[json.loads(line) for line in (a/'events.jsonl').read_text().splitlines()]
            self.assertTrue(all(e['schema_version']==2 for e in events))
            before={p.name:p.read_bytes() for p in a.iterdir()}
            p=cli('executar','--dados',DATA,'--config',CONFIG,'--saida',a)
            self.assertEqual(p.returncode,1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in a.iterdir()})

    def test_exit_codes_partial_artifacts_and_full_input_hash(self):
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,cs,code in [('last',inputs().candles[:4],2),
                                 ('gap',inputs().candles[:4]+inputs().candles[5:],1)]:
                data=root/(name+'.json')
                data.write_text(json.dumps(wire(dict(schema_version=1,candles=cs))))
                target=root/name
                p=cli('executar','--dados',data,'--config',CONFIG,'--saida',target,'--formato','json')
                self.assertEqual(p.returncode,code,p.stderr)
                self.assertTrue(p.stderr)
                r=json.loads(p.stdout)
                self.assertEqual(r['exit_code'],code)
                if name=='gap':
                    self.assertEqual(r['status'],'INTERRUPTED')
                    self.assertEqual(r['orders'][0]['status'],'NEW')
                    self.assertIsNotNone(r['pending_order_id'])
                    self.assertEqual(r['round_trip_reason'],'REPLAY_INTERRUPTED')
                    self.assertEqual(json.loads((target/'manifest.json').read_text())['data_hash'],sha256(data.read_bytes()).hexdigest())
                    self.assertIn('relatório parcial',html_report(r))
                    self.assertIn('INTERRUPTED',text_report(r))
                else:
                    self.assertEqual(r['orders'][0]['reason'],'NO_FUTURE_OPEN')
            # Estrutura inválida não cria diretório de saída.
            invalid=root/'invalid.json'; invalid.write_text('{}')
            target=root/'never-created'
            p=cli('executar','--dados',invalid,'--config',CONFIG,'--saida',target)
            self.assertEqual(p.returncode,1)
            self.assertFalse(target.exists())
        self.assertEqual(cli('executar','--estrategia','sma').returncode,2)

    def test_blocked_decision_exit_two_without_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            c=json.loads(CONFIG.read_text());c['initial_cash']='1'
            config=root/'config.json';config.write_text(json.dumps(c))
            p=cli('executar','--dados',DATA,'--config',config,'--saida',root/'out','--formato','json')
            self.assertEqual(p.returncode,2)
            r=json.loads(p.stdout)
            self.assertEqual(r['orders'],[])
            self.assertEqual(r['decisions'][0]['reason'],'INSUFFICIENT_CASH')
            self.assertIn('INSUFFICIENT_CASH',p.stderr)


if __name__=='__main__':
    unittest.main()
