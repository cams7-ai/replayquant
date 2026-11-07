"""Gráfico SMA: preenchimentos reais, resultados após taxas e dados liberados."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, Inexact, ROUND_UP, localcontext
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256

from replayquant.data import load_inputs
from replayquant.engine import replay
from replayquant.html_report import html_report
from replayquant.reporting import report, wire

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/fixtures/sprint07-candles.json'
CONFIG = ROOT / 'experiments/sprint07-sma.json'
D = Decimal


class ChartPayload(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.capture = False
        self.parts = []
        self.scripts = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.scripts.append(attrs)
            self.capture = attrs.get('id') == 'chart-data'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def payload(html):
    return json.loads(''.join(ChartPayload(html).parts))


class ResourceParser(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.external = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and not value.startswith('#'):
                self.external.append(value)


class SMAChartTests(unittest.TestCase):
    def setUp(self):
        self.inputs = load_inputs(DATA, CONFIG)

    def summary(self, candles=None, config=None):
        return report(replay(self.inputs.candles if candles is None else candles,
                             self.inputs.config if config is None else config))

    def test_candles_and_actual_fill_markers_with_net_loss(self):
        summary = self.summary()
        html = html_report(summary)
        data = payload(html)
        self.assertEqual(len(data['candles']), 8)
        self.assertEqual(len(data['executions']), 2)
        buy, sell = data['executions']
        self.assertEqual(buy['id'], summary['fills'][0].id)
        self.assertEqual((buy['classification'], sell['classification']), ('buy', 'loss'))
        self.assertEqual(D(buy['price']), D('100100'))
        self.assertEqual(D(sell['price']), D('99900'))
        self.assertIn('2026-01-01T12:04:00', buy['at'])
        self.assertIn('2026-01-01T12:07:00', sell['at'])
        self.assertIn('Perda líquida: −0,4 USDT', html)
        self.assertIn('Taxas das duas pontas: 0,2 USDT', html)
        self.assertIn('<strong class="loss">Resultado líquido', html)
        self.assertEqual(data['trades'][0]['classification'], 'loss')
        self.assertIn('aria-label="Candles BTC/USDT com compras, vendas e resultados líquidos"', html)
        self.assertEqual(ResourceParser(html).external, ['https://www.tradingview.com/'])
        self.assertEqual([s['id'] for s in ChartPayload(html).scripts],
                         ['chart-data', 'lightweight-charts-library', 'replayquant-chart-controller'])
        self.assertTrue(all('src' not in s for s in ChartPayload(html).scripts))
        self.assertIn('Apache License', html)
        self.assertIn('Copyright (c) 2019 TradingView, Inc', html)
        self.assertIn('Lightweight Charts™ 5.2.0', html)

    def test_native_axes_grid_and_navigation_are_configured(self):
        html = html_report(self.summary())
        data = payload(html)
        self.assertEqual(data['candles'][4]['time'], data['executions'][0]['time'])
        self.assertEqual(data['candles'][7]['time'], data['executions'][1]['time'])
        self.assertIn('leftPriceScale: {visible: true', html)
        self.assertIn('rightPriceScale: {visible: false}', html)
        self.assertIn('style: L.LineStyle.Dotted', html)
        self.assertIn("f.side === 'BUY' ? 'atPriceBottom' : 'atPriceTop'", html)
        self.assertIn('price: num(f.price)', html)
        self.assertIn('Preço (USDT/BTC) · Escala fixa à esquerda', html)
        for action in ('in', 'out', 'all', 'recent'):
            self.assertIn(f'data-chart-action="{action}"', html)
        self.assertIn('chart.takeScreenshot(true)', html)
        self.assertIn('Ative JavaScript para visualizar o gráfico', html)
        self.assertNotIn('chart-scroll', html)

    def test_gross_gain_can_be_net_loss_due_to_fees(self):
        candles = list(self.inputs.candles)
        candles[-1] = replace(candles[-1], open=D('100300'), high=D('100300'))
        summary = self.summary(candles)
        # Bruto SELL 100.1997 > BUY 100.1, mas as taxas transformam ganho em perda.
        self.assertGreater(summary['calculations'][1]['gross'], summary['calculations'][0]['gross'])
        self.assertEqual(summary['round_trip_result'], D('-.1005997'))
        html = html_report(summary)
        self.assertIn('Perda líquida: −0,1005997 USDT', html)
        self.assertIn('Taxas das duas pontas: 0,2002997 USDT', html)
        self.assertEqual(payload(html)['executions'][-1]['classification'], 'loss')

    def test_profit_and_break_even_colors(self):
        candles = list(self.inputs.candles)
        candles[-1] = replace(candles[-1], open=D('101000'), high=D('101000'))
        html = html_report(self.summary(candles))
        self.assertIn('Ganho líquido: 0,598001 USDT', html)
        self.assertEqual(payload(html)['executions'][-1]['classification'], 'gain')
        config = replace(self.inputs.config, fee_rate=D('0'), slippage_rate=D('0'))
        html = html_report(self.summary(config=config))
        self.assertIn('Empate líquido: 0 USDT', html)
        self.assertEqual(payload(html)['executions'][-1]['classification'], 'neutral')

    def test_no_marker_for_unexecuted_signal_or_open_position_profit(self):
        last = self.summary(self.inputs.candles[:4])
        html = html_report(last)
        self.assertEqual(payload(html)['executions'], [])
        self.assertIn('Nenhuma ida e volta encerrada', html)
        self.assertEqual(last['orders'][0].reason, 'NO_FUTURE_OPEN')
        html = html_report(self.summary(self.inputs.candles[:5]))
        self.assertEqual(len(payload(html)['executions']), 1)
        self.assertIn('posição aberta não tem ganho ou perda realizada', html)
        self.assertNotIn('class="trade-result ', html)

    def test_gap_only_shows_processed_prefix_without_future_candles(self):
        candles = self.inputs.candles[:4] + self.inputs.candles[5:]
        summary = self.summary(candles)
        self.assertEqual(summary['status'], 'INTERRUPTED')
        self.assertEqual(summary['candles'], list(self.inputs.candles[:4]))
        html = html_report(summary)
        data = payload(html)
        self.assertEqual(len(data['candles']), 4)
        self.assertEqual(data['executions'], [])
        self.assertTrue(all(c['open_time'] < '2026-01-01T12:05' for c in data['candles']))

    def test_flat_prices_empty_history_and_old_reports(self):
        candles = [replace(c, open=D('1'), high=D('1'), low=D('1'), close=D('1'))
                   for c in self.inputs.candles]
        html = html_report(self.summary(candles))
        self.assertEqual(payload(html)['executions'], [])
        self.assertNotIn('NaN', json.dumps(payload(html)))
        summary = self.summary()
        summary.pop('candles')
        self.assertIn('Nenhum candle fechado disponível', html_report(summary))

    def test_chart_preserves_context_input_and_escapes_ids(self):
        summary = wire(self.summary())
        summary['fills'][0]['id'] = '</script><script>"&</script>'
        before = deepcopy(summary)
        expected = html_report(summary)
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_UP
            ctx.traps[Inexact] = True
            ctx.flags[Inexact] = True
            snapshot = ctx.copy()
            self.assertEqual(html_report(summary), expected)
            self.assertEqual(ctx.flags, snapshot.flags)
            self.assertEqual(ctx.traps, snapshot.traps)
            self.assertEqual(ctx.prec, snapshot.prec)
        self.assertEqual(before, summary)
        self.assertNotIn('<script>', expected)
        self.assertIn(r'\u003cscript\u003e', expected)
        self.assertEqual(payload(expected)['executions'][0]['id'], summary['fills'][0]['id'])
        self.assertEqual(len(ChartPayload(expected).scripts), 3)

    def test_expanded_scenario_has_wins_loss_and_positive_closed_result(self):
        expanded = load_inputs(ROOT / 'data/fixtures/sprint07-candles-expandido.json',
                               ROOT / 'experiments/sprint07-sma-expandido.json')
        session = replay(expanded.candles, expanded.config)
        self.assertEqual(len(expanded.candles), 240)
        self.assertEqual(len(session.fills), 6)
        results = []
        for buy, sell in zip(session.fills[::2], session.fills[1::2]):
            self.assertEqual((buy.side, sell.side), ('BUY', 'SELL'))
            results.append(sell.price * sell.quantity - sell.fee
                           - buy.price * buy.quantity - buy.fee)
        self.assertTrue(any(result > 0 for result in results))
        self.assertTrue(any(result < 0 for result in results))
        self.assertEqual(sum(results), D('0.90155066834'))
        self.assertEqual(session.balance.cash, D('1000.90155066834'))
        self.assertEqual(session.balance.cash - expanded.config.initial_cash, sum(results))
        self.assertEqual(session.balance.btc, 0)
        self.assertIsNone(session.pending)
        summary = report(session)
        self.assertEqual(summary['exit_code'], 0)
        self.assertIsNone(summary['round_trip_result'])  # Contrato JSON de uma única ida e volta.
        html = html_report(summary)
        self.assertIn('Resultado líquido das operações encerradas', html)
        self.assertIn('Resultado líquido total das operações encerradas: 0,90155066834 USDT', html)
        self.assertEqual(html.count('class="trade-result gain"'), 2)
        self.assertEqual(html.count('class="trade-result loss"'), 1)
        self.assertIn('<strong class="gain">Resultado líquido das operações encerradas', html)

    def test_vendored_library_integrity_and_manifest_identity(self):
        from replayquant.reporting import manifest
        assets = ROOT / 'replayquant/assets'
        lock = json.loads((assets / 'lightweight-charts-vendor.json').read_text())
        self.assertEqual(lock['version'], '5.2.0')
        for name, expected in lock['files'].items():
            self.assertEqual(sha256((assets / name).read_bytes()).hexdigest(), expected)
        metadata = manifest(self.inputs)
        files = {f['path']: f['sha256'] for f in metadata['code_files']}
        for name in ('chart.js', 'lightweight-charts-5.2.0.standalone.production.js',
                     'lightweight-charts-NOTICE.txt', 'fancy-canvas-LICENSE.txt'):
            self.assertEqual(files[f'replayquant/assets/{name}'], sha256((assets / name).read_bytes()).hexdigest())
        self.assertEqual(metadata['frontend_dependencies'][0]['version'], '5.2.0')

    def test_cli_chart_and_persisted_candles(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out'
            p = subprocess.run([sys.executable, '-m', 'replayquant', 'executar', '--dados', str(DATA),
                                '--config', str(CONFIG), '--saida', str(target), '--formato', 'html'],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            summary = json.loads((target / 'report.json').read_text())
            self.assertEqual(len(summary['candles']), 8)
            self.assertEqual(p.stdout, html_report(summary))
            self.assertEqual(len(payload(p.stdout)['executions']), 2)
        p = subprocess.run([sys.executable, '-m', 'replayquant', 'demonstrar', '--estrategia', 'sma',
                            '--formato', 'html'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(payload(p.stdout)['executions']), 2)
        manual = load_inputs(ROOT / 'data/fixtures/sprint06-candles.json', ROOT / 'experiments/sprint06-manual.json')
        summary = report(replay(manual.candles, manual.config))
        self.assertNotIn('candles', summary)
        self.assertNotIn('<svg ', html_report(summary))


if __name__ == '__main__':
    unittest.main()
