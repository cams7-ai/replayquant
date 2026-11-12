"""Estratégias modulares: valores manuais, integração causal e compatibilidade."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D, Inexact, localcontext
from fractions import Fraction as F
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from replayquant.data import load_inputs, parse_config
from replayquant.engine import replay
from replayquant.html_report import html_report
from replayquant.reporting import canonical, manifest, report, wire, write_artifacts
from replayquant.risk_engine import RiskSession
from replayquant.strategies import REGISTRY, StrategyRegistry
from replayquant.strategy_models import CrossParameters, RSIParameters, StrategySpec
from replayquant.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def inputs(name='sma', suffix=''):
    return load_inputs(ROOT/f'data/fixtures/sprint10-candles{suffix}.json',
                       ROOT/f'experiments/sprint10-{name}.json')


def fraction(value):
    return None if value is None else F(int(value['numerator']), int(value['denominator']))


class IndicatorTests(unittest.TestCase):
    def evaluations(self, name, candles=None, spec=None):
        i = inputs(name)
        strategy = REGISTRY.create(spec or i.config.strategy)
        return [strategy.on_close(c) for c in (candles or i.candles)]

    def test_exact_manual_table_and_signals(self):
        expected = {
            'sma': ([None, 95000, 85000, 90000, 110000, 110000, 90000],
                    [None, None, 90000, 90000, 100000, F(320000, 3), 100000]),
            'ema': ([None, 95000, 85000, 95000, F(335000, 3), F(935000, 9), F(2375000, 27)],
                    [None, None, 90000, 95000, 107500, 103750, 91875]),
        }
        for name, (short, long) in expected.items():
            with self.subTest(name=name):
                rows = self.evaluations(name)
                self.assertEqual([fraction(e['short']) for e in rows], short)
                self.assertEqual([fraction(e['long']) for e in rows], long)
                self.assertEqual([(e['count'], e['side']) for e in rows if e['side']], [(5, 'BUY'), (7, 'SELL')])
                self.assertTrue(rows[2]['indicator_ready'])
                self.assertFalse(rows[2]['signal_ready'])
                self.assertEqual(rows[3]['reason'], 'NO_CROSS')
        rows = self.evaluations('rsi')
        self.assertEqual([fraction(e['rsi']) for e in rows],
                         [None, None, 0, F(200, 3), F(600, 7), 40, F(600, 31)])
        self.assertEqual([(e['count'], e['reason']) for e in rows if e['side']],
                         [(4, 'EXIT_OVERSOLD'), (6, 'EXIT_OVERBOUGHT')])

    def test_flat_one_sided_and_period_one(self):
        for prices, expected in [([100000]*7, 50), (list(range(100000, 100007)), 100),
                                 (list(range(100007, 100000, -1)), 0)]:
            candles = [replace(c, open=D(p), high=D(p), low=D(p), close=D(p))
                       for c, p in zip(inputs().candles, prices)]
            for period in [1, 2]:
                spec = StrategySpec('RSI_REVERSION', 1, RSIParameters(period, D(30), D(70)))
                rows = self.evaluations('rsi', candles, spec)
                self.assertEqual(fraction(rows[-1]['rsi']), expected)
                self.assertFalse(any(r['side'] for r in rows))
                self.assertFalse(rows[period]['signal_ready'])
        spec = StrategySpec('EMA_CROSS', 1, CrossParameters(1, 3))
        rows = self.evaluations('ema', spec=spec)
        self.assertEqual([fraction(r['short']) for r in rows], [c.close for c in inputs().candles])

    def test_equality_at_rsi_threshold_and_subdisplay_cross(self):
        spec = StrategySpec('RSI_REVERSION', 1, RSIParameters(1, D(50), D(70)))
        rows = self.evaluations('rsi', spec=spec)
        self.assertEqual([(e['count'], e['side']) for e in rows if e['side']],
                         [(4, 'BUY'), (6, 'SELL')])
        flat_prices = [100000, 100000, 100000, 110000, 110000, 110000, 110000]
        flat_candles = [replace(c, open=D(p), high=D(p), low=D(p), close=D(p))
                        for c, p in zip(inputs().candles, flat_prices)]
        rows = self.evaluations('rsi', flat_candles, spec)
        self.assertEqual([(e['count'], e['side']) for e in rows if e['side']],
                         [(4, 'BUY'), (5, 'SELL')])
        self.assertEqual(rows[5]['comparison']['oversold'], 0)
        self.assertEqual(rows[5]['reason'], 'NO_CROSS')
        candles = inputs().candles[:4]
        prices = [D('1'), D('1'), D('1'), D('1.000000000001')]
        candles = [replace(c, open=p, high=p, low=p, close=p) for c,p in zip(candles,prices)]
        for name in ['sma', 'ema']:
            row = self.evaluations(name, candles)[-1]
            if name == 'sma':
                self.assertEqual(row['short']['value'], row['long']['value'])
            self.assertEqual(row['side'], 'BUY')
            self.assertGreater(fraction(row['short']), fraction(row['long']))

    def test_indicator_duplicate_conflict_order_and_snapshot(self):
        i = inputs('ema');strategy = REGISTRY.create(i.config.strategy)
        first = strategy.on_close(i.candles[0])
        self.assertEqual(strategy.on_close(i.candles[0]), first)
        first['values']['short'] = {'adulterado': True}
        self.assertNotEqual(strategy.on_close(i.candles[0]), first)
        with self.assertRaises(ValidationError):
            strategy.on_close(replace(i.candles[0], volume=D(2)))
        with self.assertRaises(ValidationError):
            strategy.on_close(i.candles[2])
        self.assertEqual(strategy.on_close(i.candles[1])['count'], 2)

    def test_registry_validation_and_new_instances(self):
        spec = inputs('ema').config.strategy
        self.assertIsNot(REGISTRY.create(spec), REGISTRY.create(spec))
        registry = StrategyRegistry()
        with self.assertRaises(ValidationError): registry.create(spec)
        registry.register('EMA_CROSS', 1, lambda p: None)
        with self.assertRaises(ValidationError): registry.register('EMA_CROSS', 1, lambda p: None)
        for args in [('EMA_CROSS', True, CrossParameters(2,3)),
                     ('EMA_CROSS', 2, CrossParameters(2,3)),
                     ('BAD', 1, CrossParameters(2,3)),
                     ('EMA_CROSS', 1, RSIParameters(2,D(30),D(70)))]:
            with self.assertRaises(ValidationError): StrategySpec(*args)
        with self.assertRaises(ValidationError): CrossParameters(True,3)
        with self.assertRaises(ValidationError): RSIParameters(0,D(30),D(70))
        with self.assertRaises(ValidationError): RSIParameters(2,D(70),D(30))


class ModularReplayTests(unittest.TestCase):
    def test_manual_financial_examples(self):
        for name in ['sma','ema']:
            i = inputs(name);s = replay(i.candles,i.config);p = report(s)
            self.assertEqual(p['exit_code'],2)
            self.assertEqual(s.balance.cash,D('983.4'))
            self.assertEqual(s.balance.btc,D('.000166'))
            self.assertEqual(p['analysis']['metrics']['final_gross_equity']['value'],D('996.68'))
            self.assertEqual(s.orders[-1].reason,'NO_FUTURE_OPEN')
            self.assertEqual(p['schema_version'],5)
        i = inputs('rsi');s = replay(i.candles,i.config)
        self.assertEqual([o.reason for o in s.orders],['RISK_BUDGET_EXCEEDED','INSUFFICIENT_ASSET'])
        self.assertEqual(s.fills,())
        self.assertEqual(s.balance.cash,D(1000))
        i = inputs('rsi','-rsi');s = replay(i.candles,i.config);p = report(s)
        self.assertEqual(p['exit_code'],0)
        self.assertEqual(len(s.fills),2)
        self.assertEqual(s.balance.cash,D(1000))
        self.assertEqual(s.balance.btc,0)
        self.assertEqual(p['analysis']['metrics']['realized_pnl']['value'],0)
        self.assertEqual(s.ledger.reconcile()['status'],'PASSED')

    def test_schema_strictness_and_identity(self):
        raw = json.loads((ROOT/'experiments/sprint10-rsi.json').read_text())
        variants = []
        for key,value in [('version',True),('version',2),('name',[]),('parameters',{'short_window':2,'long_window':3})]:
            bad=deepcopy(raw);bad['strategy'][key]=value;variants.append(bad)
        for value in [30,True,'NaN']:
            bad=deepcopy(raw);bad['strategy']['parameters']['oversold']=value;variants.append(bad)
        bad=deepcopy(raw);bad['mode']='SMA';variants.append(bad)
        bad=deepcopy(raw);bad['orders']=[];variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValidationError): parse_config(json.dumps(bad).encode())
        with self.assertRaises(ValidationError): parse_config(b'{"schema_version":5,"schema_version":5}')
        i=inputs('rsi')
        self.assertEqual(manifest(i),manifest(i,analysis=True))
        with self.assertRaises(ValidationError): manifest(i,analysis=False)
        self.assertNotEqual(manifest(i)['run_id'],manifest(inputs('ema'))['run_id'])
        changed=replace(i.config,strategy=replace(i.config.strategy,parameters=RSIParameters(3,D(30),D(70))))
        self.assertNotEqual(manifest(i)['run_id'],manifest(replace(i,config=changed))['run_id'])

    def test_incremental_isolated_sessions_and_prefix_causality(self):
        for name in ['sma','ema','rsi']:
            i=inputs(name,'-rsi');a=RiskSession(i.config);b=RiskSession(i.config)
            for candle in i.candles:
                for s in [a,b]:
                    s.on_open(candle.opening());s.on_close(candle)
                    events=canonical(s.events)
                    s.on_close(candle)
                    self.assertEqual(canonical(s.events),events)
            a.finish();b.finish()
            expected=report(replay(i.candles,i.config))
            self.assertEqual(canonical(report(a)),canonical(expected))
            self.assertEqual(canonical(report(b)),canonical(expected))
            prefix=RiskSession(i.config)
            for c in i.candles[:4]:prefix.on_open(c.opening());prefix.on_close(c)
            snapshot=canonical(prefix.events)
            for c in i.candles[4:]:
                c=replace(c,high=c.high+D('999'))
                prefix.on_open(c.opening());prefix.on_close(c)
            self.assertEqual(canonical(prefix.events[:len(json.loads(snapshot))]),snapshot)

    def test_gap_and_atomic_failure_preserve_indicator(self):
        for name in ['ema','rsi']:
            i=inputs(name);s=RiskSession(i.config)
            for c in i.candles[:4]:s.on_open(c.opening());s.on_close(c)
            before=canonical(s.events);count=s.strategy.indicator.count
            s.on_open(i.candles[5].opening())
            self.assertEqual(s.status,'INTERRUPTED')
            self.assertEqual(s.strategy.indicator.count,count)
            self.assertEqual(canonical(s.events[:-1]),before)
            s=RiskSession(i.config);s.on_open(i.candles[0].opening())
            before=deepcopy(s.__dict__)
            with patch.object(RiskSession,'_observe',side_effect=ValidationError('injected')):
                with self.assertRaises(ValidationError):s.on_close(i.candles[0])
            self.assertEqual(canonical(s.events),canonical(before['_events']))
            self.assertEqual(s.strategy.indicator.count,0)
            from replayquant.strategies import ModularStrategy
            original = ModularStrategy.on_close
            def fail_after_indicator(strategy, candle):
                original(strategy, candle)
                raise ValidationError('injected after recurrence')
            with patch.object(ModularStrategy, 'on_close', fail_after_indicator):
                with self.assertRaises(ValidationError):
                    s.on_close(i.candles[0])
            self.assertEqual(s.strategy.indicator.count, 0)
            self.assertEqual(canonical(s.events), canonical(before['_events']))
            s.on_close(i.candles[0]);self.assertEqual(s.strategy.indicator.count,1)

    def test_protection_and_costs_reuse_financial_policy(self):
        for name in ['ema','rsi']:
            i=inputs(name,'-rsi');config=replace(i.config,fee_rate=D('.001'),slippage_rate=D('.001'))
            baseline=replay(i.candles,config)
            self.assertTrue(baseline.ledger.reconcile())
            s=RiskSession(config)
            entry_index=4 if name=='rsi' else 5
            for c in i.candles[:entry_index+1]:s.on_open(c.opening());s.on_close(c)
            if s.balance.btc:
                candle=i.candles[entry_index+1]
                stop=s.protection_groups[-1].stop
                candle=replace(candle,open=stop-D(1),low=stop-D(1))
                s.on_open(candle.opening());s.on_close(candle)
                self.assertEqual(s.balance.btc,0)
                self.assertTrue(s.ledger.reconcile())
                self.assertTrue(any(e['type']=='PROTECTION_TRIGGER' for e in s.events))

    def test_new_strategies_follow_minimum_rules(self):
        for name in ['ema', 'rsi']:
            i = inputs(name, '-rsi')
            config = replace(i.config, instrument_filters=replace(i.config.instrument_filters,
                             min_quantity=D('1')))
            s = replay(i.candles, config)
            self.assertTrue(any(o.reason == 'BELOW_MINIMUMS' for o in s.orders))
            self.assertEqual(s.balance.cash, D(1000))

    def test_cancellation_releases_reserve_and_is_idempotent(self):
        from replayquant.risk_models import RiskRequest
        for name in ['ema', 'rsi']:
            i = inputs(name, '-rsi')
            s = RiskSession(i.config)
            index = 4 if name == 'ema' else 3
            for candle in i.candles[:index+1]:
                s.on_open(candle.opening())
                s.on_close(candle)
            pending = s.pending
            self.assertIsNotNone(pending)
            request = RiskRequest('cancel', i.candles[index].close_time, 'CANCEL', pending)
            s.submit(request)
            snapshot = canonical(s.events)
            s.submit(request)
            self.assertEqual(canonical(s.events), snapshot)
            self.assertIsNone(s.pending)
            self.assertEqual(s.balance.cash, D(1000))
            self.assertEqual(s.ledger.entries[-1].cash_reserved_after, 0)
            self.assertEqual(s.fees, 0)

    def test_hostile_decimal_context(self):
        i=inputs('rsi','-rsi');expected=canonical(report(replay(i.candles,i.config)))
        with localcontext() as context:
            context.prec=2;context.traps[Inexact]=True
            flags=context.flags.copy()
            actual=canonical(report(replay(i.candles,i.config)))
            self.assertEqual(context.flags,flags)
            self.assertEqual(context.prec,2)
        self.assertEqual(actual,expected)

    def test_warmup_history_stability_is_reproducible(self):
        from replayquant.warmup import investigate
        data = ROOT/'data/fixtures/sprint07-candles-expandido.json'
        for name in ['sma', 'ema', 'rsi']:
            config = ROOT/f'experiments/sprint10-{name}.json'
            result = investigate(data, config)
            self.assertEqual(canonical(result), canonical(investigate(data, config)))
            differences = [m for row in result['comparisons']
                           for m in row['absolute_differences'].values()]
            if name == 'sma':
                self.assertTrue(all(m['numerator'] == '0' for m in differences))
            else:
                self.assertTrue(any(m['numerator'] != '0' for m in differences))

    def test_artifacts_formats_and_redundant_analysis(self):
        from replayquant.exports import markdown_report
        for name in ['sma','ema','rsi']:
            i=inputs(name);metadata=manifest(i)
            s=replay(i.candles,i.config,metadata['run_id']);p=report(s)
            self.assertEqual(p,report(s,analysis=True))
            html=html_report(p)
            self.assertIn(i.config.strategy.name,html)
            self.assertIn('indicator-chart',html)
            self.assertIn('Indicador pronto',html)
            self.assertIn('Estratégia e avaliações',markdown_report(p))
            with tempfile.TemporaryDirectory() as root:
                a,b=Path(root)/'a',Path(root)/'b'
                write_artifacts(a,metadata,s,p);write_artifacts(b,metadata,s,p)
                self.assertEqual(len(list(a.iterdir())),11)
                for file in a.iterdir():self.assertEqual(file.read_bytes(),(b/file.name).read_bytes())
                with self.assertRaises(FileExistsError):write_artifacts(a,metadata,s,p)


if __name__ == '__main__':
    unittest.main()
