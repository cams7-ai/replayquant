"""Contratos financeiros, temporais, de entrada e de reprodução da Sprint 06."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_UP, getcontext, localcontext
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.__main__ import main
from replayquant.data import load_inputs, parse_candles, parse_config
from replayquant.engine import Session, replay
from replayquant.models import Candle, Config, Fill, Opening, Request
from replayquant.portfolio import Balance, after_fill
from replayquant.reporting import canonical, manifest, report, wire, write_artifacts
from replayquant.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/fixtures/sprint06-candles.json"
CONFIG = ROOT / "experiments/sprint06-manual.json"


def encode(value):
    return json.dumps(value).encode()


class ReplayTests(unittest.TestCase):
    def setUp(self):
        inputs = load_inputs(DATA, CONFIG)
        self.candles, self.config = inputs.candles, inputs.config

    def run_session(self, **changes):
        return replay(self.candles, replace(self.config, **changes))

    def test_round_trip_and_cash_reconciliation(self):
        session = self.run_session()
        summary = report(session)
        self.assertEqual(session.balance, Balance(D("1000.799"), D("0")))
        self.assertEqual(session.fees, D("0.201"))
        self.assertEqual(summary["round_trip_result"], D("0.799"))
        self.assertEqual(summary["exit_code"], 0)
        self.assertEqual([o.status for o in session.orders], ["FILLED", "FILLED"])
        events = [e for e in session.events if e["type"] == "FILLED"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["after"], Balance(D("899.9"), D("0.001")))
        self.assertEqual([e["gross"] for e in events], [D("100"), D("101")])
        self.assertEqual([f.fee for f in session.fills], [D("0.1"), D("0.101")])
        self.assertEqual(session.balance.cash, self.config.initial_cash + summary["round_trip_result"])
        self.assertTrue(all(e["after"].cash >= 0 and e["after"].btc >= 0 for e in events))

    def test_submission_does_not_debit_and_fill_requires_next_event(self):
        session = Session(self.config, "temporal")
        session.on_open(self.candles[0].opening())
        session.on_close(self.candles[0])
        session.submit(self.config.orders[0])
        self.assertEqual(session.balance, Balance(D("1000")))
        self.assertFalse(session.fills)
        premature = Fill("compra-01:fill:1", "compra-01", "BUY", D("0.001"),
                         D("100000"), D("0.1"), self.candles[0].close_time)
        snapshot = session.events
        with self.assertRaises(ValidationError):
            session.apply_fill(premature)
        self.assertEqual(session.events, snapshot)
        session.on_open(self.candles[1].opening())
        types = [e["type"] for e in session.events]
        self.assertEqual(types, ["OPEN", "CLOSE", "SUBMITTED", "ACCEPTED", "OPEN", "FILLED"])
        self.assertEqual(session.events[1]["at"], session.events[-1]["at"])
        self.assertLess(session.orders[0].submitted_seq, session.events[-1]["seq"])
        self.assertEqual(session.balance.cash, D("899.9"))
        self.assertEqual([e["seq"] for e in session.events], list(range(1, 7)))
        for event in session.events:
            if event["type"] == "OPEN":
                self.assertFalse({"high", "low", "close", "volume", "candle"} & set(event))

    def test_fee_included_in_submission_balance_check(self):
        session = self.run_session(initial_cash=D("100"), orders=self.config.orders[:1])
        self.assertEqual(session.balance, Balance(D("100")))
        self.assertEqual(session.orders[0].reason, "INSUFFICIENT_CASH")
        self.assertEqual(session.orders[0].status, "REJECTED")
        self.assertEqual(session.fees, 0)
        self.assertFalse(session.fills)
        self.assertEqual(report(session)["exit_code"], 2)

    def test_next_open_price_revalidates_cash_without_partial_fill(self):
        candles = list(self.candles)
        candles[1] = replace(candles[1], open=D("101000"))
        session = replay(candles, replace(self.config, initial_cash=D("100.1"), orders=self.config.orders[:1]))
        self.assertIn("ACCEPTED", [e["type"] for e in session.events])
        self.assertEqual(session.orders[0].reason, "INSUFFICIENT_CASH")
        self.assertEqual(session.balance, Balance(D("100.1")))
        self.assertFalse(session.fills)
        self.assertEqual(session.fees, 0)

    def test_insufficient_asset_and_position_already_open(self):
        sell = Request("sem-btc", self.candles[0].close_time, "SELL")
        session = self.run_session(orders=(sell,))
        self.assertEqual(session.orders[0].reason, "INSUFFICIENT_ASSET")
        self.assertEqual(session.balance, Balance(D("1000")))
        buy_again = Request("compra-02", self.candles[1].close_time, "BUY")
        session = self.run_session(orders=(self.config.orders[0], buy_again))
        self.assertEqual(session.orders[1].reason, "POSITION_OPEN")
        self.assertEqual(session.balance, Balance(D("899.9"), D("0.001")))
        self.assertEqual(len(session.fills), 1)

    def test_pending_has_precedence_and_is_preserved(self):
        second = Request("concorrente", self.config.orders[0].at_close, "SELL")
        session = self.run_session(orders=(self.config.orders[0], second))
        self.assertEqual(session.orders[1].reason, "ORDER_PENDING")
        self.assertEqual(session.orders[0].status, "FILLED")
        self.assertEqual(len(session.fills), 1)
        self.assertEqual(session.fills[0].order_id, "compra-01")

    def test_last_close_order_has_no_future_open(self):
        last = Request("ultima", self.candles[-1].close_time, "BUY")
        session = self.run_session(orders=(last,))
        self.assertEqual(session.orders[0].status, "UNEXECUTED")
        self.assertEqual(session.orders[0].reason, "NO_FUTURE_OPEN")
        self.assertEqual(session.balance, Balance(D("1000")))
        self.assertEqual(session.fees, 0)
        self.assertEqual(report(session)["exit_code"], 2)

    def test_empty_and_open_position_have_no_invented_result(self):
        empty = self.run_session(orders=())
        self.assertEqual(empty.balance, Balance(D("1000")))
        self.assertEqual(empty.fees, 0)
        self.assertEqual(report(empty)["exit_code"], 0)
        self.assertIsNone(report(empty)["round_trip_result"])
        self.assertEqual(report(empty)["round_trip_reason"], "NO_CLOSED_ROUND_TRIP")
        open_position = self.run_session(orders=self.config.orders[:1])
        self.assertEqual(open_position.balance, Balance(D("899.9"), D("0.001")))
        self.assertIsNone(report(open_position)["round_trip_result"])
        self.assertEqual(report(open_position)["round_trip_reason"], "ROUND_TRIP_NOT_APPLICABLE")
        self.assertEqual(len(open_position.fills), 1)

    def test_identical_order_and_execution_are_noops_even_after_finish(self):
        session = self.run_session(orders=(self.config.orders[0], self.config.orders[0], self.config.orders[1]))
        snapshot = (session.balance, session.orders, session.events, session.fees)
        self.assertEqual(len(session.fills), 2)
        session.submit(self.config.orders[0])
        session.apply_fill(session.fills[0])
        session.finish()
        self.assertEqual(snapshot, (session.balance, session.orders, session.events, session.fees))
        with self.assertRaises(ValidationError):
            session.submit(replace(self.config.orders[0], side="SELL"))
        with self.assertRaises(ValidationError):
            session.apply_fill(replace(session.fills[0], price=D("100001")))
        self.assertEqual(snapshot, (session.balance, session.orders, session.events, session.fees))

    def test_execution_cannot_reuse_another_id_or_change_order_reference(self):
        session = self.run_session()
        original = session.fills[0]
        for invalid in (replace(original, id="outro"), replace(original, order_id="venda-01"),
                        replace(original, quantity=D("0.002")), replace(original, fee=D("0"))):
            with self.subTest(fill=invalid):
                snapshot = (session.balance, session.orders, session.events, session.fees)
                with self.assertRaises(ValidationError):
                    session.apply_fill(invalid)
                self.assertEqual(snapshot, (session.balance, session.orders, session.events, session.fees))

    def test_duplicate_candle_is_ignored_with_diagnostic(self):
        duplicate = replace(self.candles[0], open=D("100000.0"))
        session = replay((self.candles[0], duplicate, *self.candles[1:]), self.config)
        self.assertEqual(session.balance.cash, D("1000.799"))
        self.assertEqual(len(session.fills), 2)
        self.assertEqual(len([e for e in session.events if e["type"] == "OPEN"]), 3)
        self.assertEqual(session.events[0]["reason"], "DUPLICATE_CANDLE")
        with self.assertRaises(ValidationError):
            replay((self.candles[0], replace(duplicate, volume=D("2")), *self.candles[1:]), self.config)

    def test_causal_fill_and_prefix_independent_of_future_ohlcv(self):
        baseline = self.run_session()
        changed = list(self.candles)
        changed[1] = replace(changed[1], high=D("999999"), low=D("1"), close=D("200000"), volume=D("0"))
        changed[2] = replace(changed[2], high=D("999999"), low=D("1"), close=D("300000"), volume=D("0"))
        alternative = replay(changed, self.config)
        self.assertEqual(baseline.fills, alternative.fills)
        first_fill_seq = next(e["seq"] for e in baseline.events if e["type"] == "FILLED")
        self.assertEqual(baseline.events[:first_fill_seq], alternative.events[:first_fill_seq])
        shortened = replay(self.candles[:2], replace(self.config, orders=self.config.orders[:1]))
        self.assertEqual(baseline.events[:first_fill_seq], shortened.events[:first_fill_seq])
        self.assertEqual(len(alternative.fills), 2)  # Volume zero não limita a hipótese fictícia.

    def test_external_decimal_context_is_preserved(self):
        with localcontext() as external:
            external.prec = 2
            external.rounding = ROUND_UP
            external.traps[Inexact] = True
            external.flags[Inexact] = True
            before = (external.prec, external.rounding, dict(external.traps), dict(external.flags))
            session = self.run_session()
            summary = wire(report(session))
            self.assertEqual(D(summary["final_balance"]["cash"]), D("1000.799"))
            after = (external.prec, external.rounding, dict(external.traps), dict(external.flags))
            self.assertEqual(before, after)

    def test_inexact_balance_change_is_atomic(self):
        balance = Balance(D("999999999999999999"))
        fill = Fill("tiny:fill:1", "tiny", "BUY", D("0.000000000001"),
                    D("0.000000000001"), D("0"), self.candles[0].close_time)
        with self.assertRaises(ValidationError):
            after_fill(balance, fill)
        self.assertEqual(balance, Balance(D("999999999999999999")))
        config = replace(self.config, initial_cash=balance.cash, quantity=fill.quantity,
                         fee_rate=D("0"), orders=self.config.orders[:1])
        session = Session(config, "atomic")
        tiny = replace(self.candles[0], open=fill.price, high=fill.price, low=fill.price, close=fill.price)
        session.on_open(tiny.opening())
        session.on_close(tiny)
        session.submit(config.orders[0])
        before = (session.balance, session.orders, session.fills, session.fees)
        with self.assertRaises(ValidationError):
            session.on_open(Opening("FICTICIA", "BTCUSDT", "1m", tiny.close_time, fill.price))
        self.assertEqual(before, (session.balance, session.orders, session.fills, session.fees))

    def test_inexact_submission_preserves_history_and_pending(self):
        price = D("999999999999999999")
        config = replace(self.config, quantity=price, fee_rate=D("0.123456789123"))
        candle = replace(self.candles[0], open=price, high=price, low=price, close=price)
        session = Session(config, "atomic-submit")
        session.on_open(candle.opening())
        session.on_close(candle)
        before = (session.balance, session.orders, session.events, session.pending)
        with self.assertRaises(ValidationError):
            session.submit(config.orders[0])
        self.assertEqual(before, (session.balance, session.orders, session.events, session.pending))

    def test_api_event_order_and_snapshot_isolation(self):
        session = Session(self.config, "api")
        with self.assertRaises(ValidationError):
            session.on_close(self.candles[0])
        with self.assertRaises(ValidationError):
            session.submit(self.config.orders[0])
        with self.assertRaises(ValidationError):
            session.on_open(self.candles[0])  # Candle inteiro não é Opening.
        session.on_open(self.candles[0].opening())
        with self.assertRaises(ValidationError):
            session.on_open(self.candles[1].opening())
        snapshot = session.events
        snapshot[0]["price"] = D("1")
        self.assertEqual(session.events[0]["price"], D("100000"))
        session.on_close(self.candles[0])
        before = session.events
        with self.assertRaises(ValidationError):
            session.on_open(self.candles[2].opening())
        self.assertEqual(before, session.events)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_bytes())
        self.config = json.loads(CONFIG.read_bytes())

    def test_invalid_json_envelopes_and_duplicate_keys(self):
        for raw in (b'{', b'[]', b'{"schema_version":1,"candles":[],"schema_version":1}',
                    b'{"schema_version":true,"candles":[]}', b'{"schema_version":1.0,"candles":[]}',
                    b'{"schema_version":"1","candles":[]}', b'{"schema_version":2,"candles":[]}',
                    b'{"schema_version":1,"candles":NaN}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                parse_candles(raw)
        duplicate = DATA.read_bytes().replace(b'"volume": "1"', b'"volume": "1", "volume": "1"', 1)
        with self.assertRaises(ValidationError):
            parse_candles(duplicate)
        for value in ([], {}, {**self.data, "extra": 1}, {**self.data, "candles": []},
                      {**self.data, "candles": {}}, {**self.data, "candles": [1]}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_candles(encode(value))

    def test_invalid_candle_values(self):
        cases = [("open", 100000.0), ("open", True), ("open", "NaN"), ("open", "Infinity"),
                 ("open", "sNaN"), ("open", "1e5"), ("open", " 100000"), ("open", "1,0"),
                 ("open", "1_000"), ("open", "-1"), ("open", "0"),
                 ("open", "1234567890123456789"), ("open", "0.0000000000001"),
                 ("open", "100000.0000000000000"), ("volume", "-1"),
                 ("is_closed", False), ("is_closed", 1), ("low", "100001"),
                 ("high", "99999"), ("symbol", "ETHUSDT"), ("interval", "5m"),
                 ("source", "REAL"), ("open_time", "2026-01-01T12:00:00"),
                 ("open_time", "2026-01-01T12:00:01+00:00"),
                 ("close_time", "2026-01-01T12:02:00+00:00")]
        for key, value in cases:
            obj = deepcopy(self.data)
            obj["candles"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                parse_candles(encode(obj))
        for mutate in (lambda c: c.pop("volume"), lambda c: c.update(extra="1")):
            obj = deepcopy(self.data)
            mutate(obj["candles"][0])
            with self.assertRaises(ValidationError):
                parse_candles(encode(obj))

    def test_out_of_order_gaps_and_conflicts(self):
        for candles in ([self.data["candles"][1], self.data["candles"][0]],
                        [self.data["candles"][0], self.data["candles"][2]],
                        [self.data["candles"][0], {**self.data["candles"][0], "volume": "2"}]):
            with self.subTest(candles=candles), self.assertRaises(ValidationError):
                parse_candles(encode({"schema_version": 1, "candles": candles}))

    def test_invalid_config_and_schedule(self):
        for key, value in (("initial_cash", "0"), ("initial_cash", True), ("quantity", "0"),
                           ("quantity", 0.001), ("fee_rate", "1"), ("fee_rate", "-0.1"),
                           ("fee_rate", "NaN"), ("slippage_rate", "0.001"),
                           ("orders", {}), ("schema_version", True)):
            obj = deepcopy(self.config)
            obj[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                parse_config(encode(obj))
        for change in ({"id": ""}, {"id": " x"}, {"side": "buy"}, {"at_close": "invalid"},
                       {"extra": 1}):
            obj = deepcopy(self.config)
            obj["orders"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                parse_config(encode(obj))
        for orders in (list(reversed(self.config["orders"])),
                       [self.config["orders"][0], {**self.config["orders"][0], "side": "SELL"}]):
            obj = {**self.config, "orders": orders}
            with self.assertRaises(ValidationError):
                parse_config(encode(obj))
        obj = deepcopy(self.config)
        obj["orders"][0]["at_close"] = "2026-01-01T11:59:00+00:00"
        config = parse_config(encode(obj))
        with self.assertRaises(ValidationError):
            replay(parse_candles(encode(self.data))[0], config)
        for obj in ({**self.config, "extra": 1}, {k: v for k, v in self.config.items() if k != "quantity"}):
            with self.assertRaises(ValidationError):
                parse_config(encode(obj))
        duplicate = CONFIG.read_bytes().replace(b'"side": "BUY"', b'"side": "BUY", "side": "BUY"')
        with self.assertRaises(ValidationError):
            parse_config(duplicate)

    def test_utc_equivalence_and_direct_python_api_validation(self):
        baseline, _ = parse_candles(encode(self.data))
        changed = deepcopy(self.data)
        for candle in changed["candles"]:
            for field in ("open_time", "close_time"):
                candle[field] = datetime.fromisoformat(candle[field]).astimezone(
                    timezone(timedelta(hours=-3))).isoformat()
        candles, _ = parse_candles(encode(changed))
        self.assertEqual(candles, baseline)
        self.assertEqual(wire(candles[0])["open_time"], "2026-01-01T12:00:00.000000+00:00")
        for value in (1.0, True, D("NaN"), D("sNaN"), D("Infinity"), D("-1")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                replace(baseline[0], open=value)
        with self.assertRaises(ValidationError):
            replace(baseline[0], open_time=datetime(2026, 1, 1, 12))
        config = parse_config(encode(self.config))
        for changes in ({"initial_cash": 1.0}, {"quantity": True}, {"orders": []}, {"fee_rate": D("1")}):
            with self.assertRaises(ValidationError):
                replace(config, **changes)
        with self.assertRaises(ValidationError):
            replay([{}], config)


class ArtifactAndCLITests(unittest.TestCase):
    def call_cli(self, *args, cwd=ROOT):
        return subprocess.run([sys.executable, "-m", "replayquant", *args], cwd=cwd,
                              capture_output=True, text=True)

    def test_help_and_demonstration_formats(self):
        self.assertEqual(self.call_cli("--help").returncode, 0)
        text = self.call_cli("demonstrar", "--formato", "texto")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("bruto = preço × quantidade", text.stdout)
        self.assertIn("Liquidez ilimitada", text.stdout)
        data = self.call_cli("demonstrar", "--formato", "json")
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertEqual(data.stderr, "")
        self.assertEqual(D(json.loads(data.stdout)["round_trip_result"]), D("0.799"))
        self.assertEqual(self.call_cli("executar").returncode, 2)
        self.assertEqual(self.call_cli("demonstrar", "--formato", "xml").returncode, 2)

    def test_reproducible_artifacts_and_independent_hash_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = [Path(temp) / "a", Path(temp) / "b"]
            for output in outputs:
                result = self.call_cli("executar", "--dados", str(DATA), "--config", str(CONFIG),
                                       "--saida", str(output), "--formato", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(set(p.name for p in output.iterdir()),
                                 {"manifest.json", "events.jsonl", "report.json"})
                self.assertEqual(json.loads(result.stdout), json.loads((output / "report.json").read_bytes()))
            for name in ("manifest.json", "events.jsonl", "report.json"):
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())
            metadata = json.loads((outputs[0] / "manifest.json").read_bytes())
            self.assertEqual(metadata["data_hash"], sha256(DATA.read_bytes()).hexdigest())
            self.assertEqual(metadata["config_hash"], sha256(CONFIG.read_bytes()).hexdigest())
            expected_paths = sorted([p.relative_to(ROOT).as_posix() for p in (ROOT / "replayquant").rglob("*.py")]
                                    + ["pyproject.toml", "requirements.lock", ".python-version"])
            self.assertEqual([f["path"] for f in metadata["code_files"]], expected_paths)
            for item in metadata["code_files"]:
                self.assertEqual(item["sha256"], sha256((ROOT / item["path"]).read_bytes()).hexdigest())
            canonical_files = json.dumps(metadata["code_files"], sort_keys=True, separators=(",", ":")).encode()
            self.assertEqual(metadata["code_hash"], sha256(canonical_files).hexdigest())
            identity = {k: metadata[k] for k in ("data_hash", "config_hash", "code_hash", "python_version")}
            self.assertEqual(metadata["run_id"], sha256(json.dumps(identity, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest())
            events = [json.loads(line) for line in (outputs[0] / "events.jsonl").read_text().splitlines()]
            self.assertTrue(all(e["schema_version"] == 1 and e["run_id"] == metadata["run_id"] for e in events))
            self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))
            original = {p.name: p.read_bytes() for p in outputs[0].iterdir()}
            refused = self.call_cli("executar", "--dados", str(DATA), "--config", str(CONFIG),
                                    "--saida", str(outputs[0]))
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(original, {p.name: p.read_bytes() for p in outputs[0].iterdir()})

    def test_cli_policy_failures_and_invalid_input_do_not_hide_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            raw = json.loads(CONFIG.read_bytes())
            for name, changes, reason in (
                ("rejeitada", {"initial_cash": "100", "orders": raw["orders"][:1]}, "INSUFFICIENT_CASH"),
                ("ultima", {"orders": [{"id": "ultima", "at_close": "2026-01-01T12:03:00+00:00", "side": "BUY"}]}, "NO_FUTURE_OPEN"),
            ):
                config = temp / f"{name}.json"
                config.write_bytes(encode({**raw, **changes}))
                output = temp / name
                result = self.call_cli("executar", "--dados", str(DATA), "--config", str(config),
                                       "--saida", str(output), "--formato", "json")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(reason, result.stderr)
                self.assertEqual(json.loads(result.stdout)["exit_code"], 2)
                self.assertTrue((output / "manifest.json").exists())
            invalid = temp / "invalid.json"
            invalid.write_text('{"schema_version":true}')
            output = temp / "nao-criar"
            for data in (invalid, temp / "ausente.json"):
                result = self.call_cli("executar", "--dados", str(data), "--config", str(CONFIG), "--saida", str(output))
                self.assertEqual(result.returncode, 1)
                self.assertFalse(output.exists())
            # Arquivo existente e symlink também são recusados sem alteração.
            output.write_text("preservar")
            result = self.call_cli("executar", "--dados", str(DATA), "--config", str(CONFIG), "--saida", str(output))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_text(), "preservar")
            link = temp / "link"
            link.symlink_to(output)
            result = self.call_cli("executar", "--dados", str(DATA), "--config", str(CONFIG), "--saida", str(link))
            self.assertEqual(result.returncode, 1)
            self.assertTrue(link.is_symlink())
            self.assertEqual(output.read_text(), "preservar")

    def test_write_failure_is_technical_and_marks_incomplete_output(self):
        inputs = load_inputs(DATA, CONFIG)
        metadata = manifest(inputs)
        session = replay(inputs.candles, inputs.config, metadata["run_id"])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "incompleta"
            with patch.object(Path, "replace", side_effect=OSError("Falha fictícia de gravação")):
                with self.assertRaises(OSError):
                    write_artifacts(output, metadata, session, report(session))
            self.assertTrue((output / "INCOMPLETE").is_file())
            self.assertFalse((output / "manifest.json").exists())
        with patch("replayquant.__main__.write_artifacts", side_effect=OSError("Falha fictícia")):
            with patch("sys.stderr") as error, patch("sys.stdout"):
                self.assertEqual(main(["executar", "--dados", str(DATA), "--config", str(CONFIG),
                                       "--saida", "unused"]), 1)
                self.assertTrue(error.write.called)

    def test_unexpected_failure_propagates_instead_of_becoming_rejection(self):
        with patch("replayquant.__main__.replay", side_effect=RuntimeError("falha inesperada")):
            with self.assertRaises(RuntimeError):
                main(["demonstrar"])

    def test_no_network_or_neighbor_dependency_and_relocation(self):
        inputs = load_inputs(DATA, CONFIG)
        with patch("socket.socket", side_effect=AssertionError("Rede proibida")):
            self.assertEqual(report(replay(inputs.candles, inputs.config))["exit_code"], 0)
        with tempfile.TemporaryDirectory() as temp:
            relocated = Path(temp) / "outro nome"
            relocated.mkdir()
            for name in ("replayquant", "data", "experiments"):
                shutil.copytree(ROOT / name, relocated / name, ignore=shutil.ignore_patterns("__pycache__"))
            for name in ("pyproject.toml", "requirements.lock", ".python-version"):
                shutil.copyfile(ROOT / name, relocated / name)
            original = self.call_cli("demonstrar", "--formato", "json")
            moved = self.call_cli("demonstrar", "--formato", "json", cwd=relocated)
            self.assertEqual(moved.returncode, 0, moved.stderr)
            self.assertEqual(original.stdout, moved.stdout)


if __name__ == "__main__":
    unittest.main()
