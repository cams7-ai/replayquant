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
from xml.etree import ElementTree as ET

from replayquant.data import load_inputs
from replayquant.engine import replay
from replayquant.html_report import html_report
from replayquant.reporting import report, wire

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/fixtures/sprint07-candles.json'
CONFIG = ROOT / 'experiments/sprint07-sma.json'
NS = {'s': 'http://www.w3.org/2000/svg'}
D = Decimal


def svg(html):
    return ET.fromstring(html[html.index('<svg '):html.index('</svg>') + 6])


def markers(tree):
    return [g for g in tree.findall('s:g', NS) if 'execution-marker' in g.get('class', '')]


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
        tree = svg(html)
        candles = [g for g in tree.findall('s:g', NS) if g.get('class') == 'candle']
        self.assertEqual(len(candles), 8)
        self.assertEqual(len(markers(tree)), 2)
        buy, sell = markers(tree)
        self.assertEqual(buy.get('data-execution-id'), summary['fills'][0].id)
        self.assertIn('buy', buy.get('class'))
        self.assertIn('loss', sell.get('class'))
        self.assertIn('100100.000 USDT/BTC', ''.join(buy.itertext()))
        self.assertIn('99900.000 USDT/BTC', ''.join(sell.itertext()))
        self.assertIn('2026-01-01T12:04:00', ''.join(buy.itertext()))
        self.assertIn('2026-01-01T12:07:00', ''.join(sell.itertext()))
        self.assertIn('Perda líquida: −0,4 USDT', html)
        self.assertIn('Taxas das duas pontas: 0,2 USDT', html)
        self.assertIn('<strong class="loss">Resultado líquido', html)
        self.assertIn('trade-link loss', html)
        self.assertIn('aria-labelledby="chart-title chart-desc"', html)
        self.assertEqual(ResourceParser(html).external, [])
        self.assertNotIn('<script', html)

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
        self.assertIn('loss', markers(svg(html))[-1].get('class'))

    def test_profit_and_break_even_colors(self):
        candles = list(self.inputs.candles)
        candles[-1] = replace(candles[-1], open=D('101000'), high=D('101000'))
        html = html_report(self.summary(candles))
        self.assertIn('Ganho líquido: 0,598001 USDT', html)
        self.assertIn('gain', markers(svg(html))[-1].get('class'))
        config = replace(self.inputs.config, fee_rate=D('0'), slippage_rate=D('0'))
        html = html_report(self.summary(config=config))
        self.assertIn('Empate líquido: 0 USDT', html)
        self.assertIn('neutral', markers(svg(html))[-1].get('class'))

    def test_no_marker_for_unexecuted_signal_or_open_position_profit(self):
        last = self.summary(self.inputs.candles[:4])
        html = html_report(last)
        self.assertEqual(markers(svg(html)), [])
        self.assertIn('Nenhuma ida e volta encerrada', html)
        self.assertEqual(last['orders'][0].reason, 'NO_FUTURE_OPEN')
        html = html_report(self.summary(self.inputs.candles[:5]))
        self.assertEqual(len(markers(svg(html))), 1)
        self.assertIn('posição aberta não tem ganho ou perda realizada', html)
        self.assertNotIn('class="trade-result ', html)

    def test_gap_only_shows_processed_prefix_without_future_candles(self):
        candles = self.inputs.candles[:4] + self.inputs.candles[5:]
        summary = self.summary(candles)
        self.assertEqual(summary['status'], 'INTERRUPTED')
        self.assertEqual(summary['candles'], list(self.inputs.candles[:4]))
        html = html_report(summary)
        tree = svg(html)
        self.assertEqual(len([g for g in tree.findall('s:g', NS) if g.get('class') == 'candle']), 4)
        self.assertEqual(markers(tree), [])
        self.assertNotIn('data-open-time="2026-01-01T12:05', html)

    def test_flat_prices_empty_history_and_old_reports(self):
        candles = [replace(c, open=D('1'), high=D('1'), low=D('1'), close=D('1'))
                   for c in self.inputs.candles]
        html = html_report(self.summary(candles))
        self.assertEqual(markers(svg(html)), [])
        self.assertNotIn('NaN', html)
        summary = self.summary()
        summary.pop('candles')
        self.assertIn('Nenhum candle fechado disponível', html_report(summary))

    def test_chart_preserves_context_input_and_escapes_ids(self):
        summary = wire(self.summary())
        summary['fills'][0]['id'] = '<script>"&</script>'
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
        self.assertIn('&lt;script&gt;', expected)
        svg(expected)  # SVG permanece XML válido.

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
            self.assertEqual(len(markers(svg(p.stdout))), 2)
        p = subprocess.run([sys.executable, '-m', 'replayquant', 'demonstrar', '--estrategia', 'sma',
                            '--formato', 'html'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(markers(svg(p.stdout))), 2)
        manual = load_inputs(ROOT / 'data/fixtures/sprint06-candles.json', ROOT / 'experiments/sprint06-manual.json')
        summary = report(replay(manual.candles, manual.config))
        self.assertNotIn('candles', summary)
        self.assertNotIn('<svg ', html_report(summary))


if __name__ == '__main__':
    unittest.main()
