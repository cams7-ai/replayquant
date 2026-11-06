"""Contratos de apresentação HTML e integração com a CLI."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from replayquant.data import load_inputs
from replayquant.engine import replay
from replayquant.html_report import html_report
from replayquant.reporting import report, wire


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/fixtures/sprint06-candles.json"
CONFIG = ROOT / "experiments/sprint06-manual.json"


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []
        self.external = []
        self.stack = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            if key in ("src", "href") and not value.startswith("#"):
                self.external.append(value)
        if tag not in ("meta", "br", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError(f"Tag desbalanceada: {tag}")

    def handle_data(self, data):
        self.text.append(data)


class HTMLReportTests(unittest.TestCase):
    def setUp(self):
        self.inputs = load_inputs(DATA, CONFIG)

    def summary(self, **changes):
        return report(replay(self.inputs.candles, replace(self.inputs.config, **changes)))

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "replayquant", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_demonstration_is_complete_offline_document_with_exact_calculations(self):
        result = self.cli("demonstrar", "--formato", "html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.startswith('<!doctype html>'))
        document = Document(result.stdout)
        self.assertEqual(document.stack, [])
        self.assertEqual(document.external, [])
        self.assertNotIn("script", document.tags)
        text = ''.join(document.text)
        for expected in ("1000,799000 USDT", "0,201000 USDT", "0,799000 USDT",
                         "100,899000 USDT − 100,100000 USDT = 0,799000 USDT",
                         "Preenchida (FILLED)", "Memória de cálculo", "Liquidez ilimitada",
                         "2026-01-01T12:01:00.000000+00:00"):
            self.assertIn(expected, text)
        self.assertIn('@media print', result.stdout)
        self.assertIn('@media(max-width:720px)', result.stdout)
        self.assertIn('lang="pt-BR"', result.stdout)

    def test_empty_and_open_positions_do_not_invent_result(self):
        for orders, reason in (((), "NO_CLOSED_ROUND_TRIP"),
                               (self.inputs.config.orders[:1], "ROUND_TRIP_NOT_APPLICABLE")):
            with self.subTest(reason=reason):
                output = html_report(self.summary(orders=orders))
                self.assertIn(f"Indisponível ({reason})", output)
                if not orders:
                    self.assertIn("Nenhuma ordem solicitada", output)
                    self.assertIn("Nenhum preenchimento realizado", output)
                else:
                    self.assertIn("0,001 BTC", output)

    def test_escaping_and_decimal_context_are_preserved(self):
        summary = wire(self.summary())
        attack = '<script>alert("x")</script>&'
        summary["run_id"] = attack
        summary["orders"][0]["request"]["id"] = attack
        summary["orders"][0]["reason"] = attack
        summary["fills"][0]["order_id"] = attack
        summary["calculations"][0]["order_id"] = attack
        summary["limitations"].append(attack)
        summary["final_balance"]["cash"] = Decimal("12345678901234567890.123456789012345678")
        before = deepcopy(summary)
        with localcontext() as context:
            context.prec = 2
            output = html_report(summary)
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;', output)
        self.assertIn('12345678901234567890,123456789012345678 USDT', output)
        self.assertEqual(summary, before)
        self.assertEqual(output, html_report(summary))
        self.assertEqual(Document(output).stack, [])

    def test_execute_preserves_artifacts_diagnostics_and_exit_codes(self):
        raw = json.loads(CONFIG.read_bytes())
        cases = (
            ("sucesso", {}, 0, None),
            ("rejeitada", {"initial_cash": "100", "orders": raw["orders"][:1]}, 2, "INSUFFICIENT_CASH"),
            ("ultima", {"orders": [{"id": "ultima", "at_close": "2026-01-01T12:03:00+00:00",
                                      "side": "BUY"}]}, 2, "NO_FUTURE_OPEN"),
        )
        with tempfile.TemporaryDirectory() as temp:
            for name, changes, code, reason in cases:
                with self.subTest(name=name):
                    config = Path(temp) / f"{name}.json"
                    config.write_text(json.dumps({**raw, **changes}), encoding="utf-8")
                    target = Path(temp) / name
                    result = self.cli("executar", "--dados", str(DATA), "--config", str(config),
                                      "--saida", str(target), "--formato", "html")
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual({p.name for p in target.iterdir()},
                                     {"manifest.json", "events.jsonl", "report.json"})
                    summary = json.loads((target / "report.json").read_bytes())
                    self.assertEqual(result.stdout, html_report(summary))
                    if reason:
                        self.assertIn(reason, result.stderr)
                        self.assertIn(reason, result.stdout)
                    else:
                        self.assertEqual(result.stderr, "")
                    refused = self.cli("executar", "--dados", str(DATA), "--config", str(config),
                                       "--saida", str(target), "--formato", "html")
                    self.assertEqual(refused.returncode, 1)
                    self.assertEqual(refused.stdout, "")
            missing = self.cli("executar", "--dados", str(Path(temp) / "missing.json"),
                               "--config", str(CONFIG), "--saida", str(Path(temp) / "unused"),
                               "--formato", "html")
            self.assertEqual(missing.returncode, 1)
            self.assertEqual(missing.stdout, "")
            self.assertFalse((Path(temp) / "unused").exists())


if __name__ == "__main__":
    unittest.main()
