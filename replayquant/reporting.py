"""Relatórios, identidade por conteúdo e gravação sem sobrescrita."""
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import platform
from . import __version__
from .models import SMAConfig
from .validation import ValidationError, financial


def wire(value):
    if isinstance(value, Decimal):
        # format não usa o contexto decimal nem arredonda o valor.
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if is_dataclass(value):
        return wire(asdict(value))
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(item) for item in value]
    return value


def canonical(value):
    return json.dumps(wire(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def json_text(value):
    return json.dumps(wire(value), indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"


def manifest(inputs):
    root = Path(__file__).resolve().parent.parent
    paths = sorted([p.relative_to(root).as_posix() for p in (root / "replayquant").rglob("*.py")]
                   + ["pyproject.toml", "requirements.lock", ".python-version"])
    code_files = [{"path": path, "sha256": sha256((root / path).read_bytes()).hexdigest()}
                  for path in paths]
    identity = {"data_hash": inputs.data_hash, "config_hash": inputs.config_hash,
                "code_hash": sha256(canonical(code_files)).hexdigest(),
                "python_version": platform.python_version()}
    metadata = {"schema_version": 1, "run_id": sha256(canonical(identity)).hexdigest(),
            **identity, "code_files": code_files, "package_version": __version__,
            "dependencies": [], "decimal_policy": {"precision": 40, "rounding": "ROUND_HALF_EVEN",
                                                     "inexact": "ERROR"},
            "execution_model": "NEXT_OPEN_FULL_UNLIMITED_LIQUIDITY",
            "fee_rate": inputs.config.fee_rate, "slippage_rate": inputs.config.slippage_rate,
            "seed": None, "seed_reason": "NO_RANDOMNESS"}
    if isinstance(inputs.config, SMAConfig):
        metadata.update(schema_version=2, strategy=inputs.config.strategy,
                        warmup_candles=inputs.config.strategy.long_window + 1,
                        temporal_policy="CLOSE_EVALUATE_DECIDE_OPEN_FILL_ZERO_LATENCY",
                        gap_policy="INTERRUPT_PRESERVE_STATE")
    return metadata


@financial
def report(session):
    sma = isinstance(session.config, SMAConfig)
    interrupted = sma and session.status == "INTERRUPTED"
    if not session.finished and not interrupted:
        raise ValidationError("Relatório final exige sessão encerrada")
    fills = session.fills
    result = None
    reason = "NO_CLOSED_ROUND_TRIP" if not fills else "ROUND_TRIP_NOT_APPLICABLE"
    calculations = []
    for fill in fills:
        gross = fill.price * fill.quantity
        cash_amount = gross + fill.fee if fill.side == "BUY" else gross - fill.fee
        calculations.append({"order_id": fill.order_id, "side": fill.side,
                             "price": fill.price, "quantity": fill.quantity,
                             "gross": gross, "fee": fill.fee, "cash_amount": cash_amount,
                             "unit": "USDT"})
    if (not interrupted and len(fills) == 2 and fills[0].side == "BUY" and fills[1].side == "SELL"
            and fills[0].quantity == fills[1].quantity and session.balance.btc == 0):
        result = calculations[1]["cash_amount"] - calculations[0]["cash_amount"]
        reason = None
    incomplete = any(o.status in ("REJECTED", "UNEXECUTED") for o in session.orders)
    summary = {"schema_version": 1, "run_id": session.run_id,
            "exit_code": 2 if incomplete else 0,
            "initial_cash": session.config.initial_cash, "final_balance": session.balance,
            "total_fees": session.fees, "round_trip_result": result,
            "round_trip_reason": reason, "orders": session.orders, "fills": fills,
            "calculations": calculations,
            "units": {"cash": "USDT", "btc": "BTC", "price": "USDT/BTC", "fee": "USDT"},
            "limitations": ["Dados fictícios; ordens manuais, sem avaliação de estratégia.",
                            "Liquidez ilimitada assumida, sem modelo de spread; slippage configurado zero.",
                            "Sem reservas, execução parcial, marcação a mercado ou liquidação forçada.",
                            "USDT não é o próprio dólar; taxas cobradas em USDT."]}
    if sma:
        events = session.events
        blocked = any(e["type"] == "DECISION" and not e["approved"] for e in events)
        summary.update(schema_version=2, status=session.status,
                       exit_code=1 if interrupted else (2 if incomplete or blocked else 0),
                       strategy=session.config.strategy, pending_order_id=session.pending,
                       diagnostic=session.diagnostic,
                       evaluations=[e for e in events if e["type"] == "EVALUATION"],
                       signals=[e for e in events if e["type"] == "SIGNAL"],
                       decisions=[e for e in events if e["type"] == "DECISION"],
                       intentions=[e for e in events if e["type"] == "INTENTION"])
        if interrupted:
            summary.update(round_trip_result=None, round_trip_reason="REPLAY_INTERRUPTED")
        for calc, fill in zip(calculations, fills):
            event = next(e for e in events if e["type"] == "FILLED" and e["execution_id"] == fill.id)
            calc.update(reference_price=event["reference_price"],
                        effective_price=fill.price, fee_rate=session.config.fee_rate,
                        slippage_rate=session.config.slippage_rate)
        summary["limitations"] = [
            "Dados fictícios; SMA causal para conferência, sem evidência de rentabilidade.",
            "Liquidez ilimitada assumida, sem modelo de spread; slippage fixo adverso já no preço.",
            "Sem reservas, execução parcial, marcação a mercado ou liquidação forçada.",
            "Latência zero entre eventos ordenados; disponibilidade completa assumida no fechamento.",
            "USDT não é o próprio dólar; taxas cobradas em USDT."]
    return summary


def ratio_text(value):
    if value is None:
        return "indisponível (WARMUP)"
    return value["numerator"] if value["denominator"] == "1" else f"{value['numerator']}/{value['denominator']}"


def text_report(value):
    value = wire(value)
    lines = ["ReplayQuant — Sprint 07" if value["schema_version"] == 2 else "ReplayQuant — Sprint 06", f"Execução: {value['run_id']}",
             f"Caixa inicial: {value['initial_cash']} USDT"]
    if value["schema_version"] == 2:
        lines.extend([f"Estado: {value['status']}; código: {value['exit_code']}",
                      f"Pendência: {value['pending_order_id'] or 'nenhuma'}",
                      f"Diagnóstico: {value['diagnostic']}"])
        lines.append("Avaliações — médias exatas (USDT/BTC); aquecimento exige longa + 1 fechamentos")
        for e in value["evaluations"]:
            lines.append(f"  {e['evaluation_id']} em {e['at']} [seq {e['seq']}]: "
                         f"curta={ratio_text(e['short'])}; longa={ratio_text(e['long'])}; "
                         f"comparação anterior={e['previous_comparison']}; atual={e['comparison']}; "
                         f"{e['side'] or e['reason']}")
        lines.append("Sinais")
        for e in value["signals"]:
            lines.append(f"  {e['signal_id']}: {e['side']} em {e['at']}; avaliação {e['evaluation_id']}")
        lines.append("Decisões")
        for e in value["decisions"]:
            lines.append(f"  {e['decision_id']}: {'aprovada' if e['approved'] else e['reason']}; "
                         f"sinal {e['signal_id']}; ordem {e['order_id'] or 'nenhuma'}")
        lines.append("Intenções")
        for e in value["intentions"]:
            lines.append(f"  {e['intent_id']}: decisão {e['decision_id']}; ordem {e['order_id']}")
    for calc in value["calculations"]:
        lines.extend([f"{calc['side']} {calc['order_id']}: {calc['quantity']} BTC a {calc['price']} USDT/BTC",
                      f"  bruto = preço × quantidade = {calc['gross']} USDT",
                      f"  taxa = bruto × alíquota = {calc['fee']} USDT",
                      f"  {'Desembolso = bruto + taxa' if calc['side'] == 'BUY' else 'Recebimento = bruto - taxa'} = {calc['cash_amount']} USDT"])
        if value["schema_version"] == 2:
            lines.append(f"  referência: {calc['reference_price']}; efetivo: {calc['effective_price']} USDT/BTC; "
                         f"slippage: {calc['slippage_rate']}; taxa: {calc['fee_rate']}")
    for fill in value["fills"]:
        if value["schema_version"] == 2:
            lines.append(f"Execução {fill['id']} da ordem {fill['order_id']} em {fill['at']}")
    for order in value["orders"]:
        lines.append(f"Ordem {order['request']['id']}: {order['status']} ({order['reason'] or 'sem rejeição'})")
    balance = value["final_balance"]
    lines.extend([f"Taxas totais: {value['total_fees']} USDT",
                  f"Caixa final: {balance['cash']} USDT; posição final: {balance['btc']} BTC"])
    if value["round_trip_result"] is None:
        lines.append(f"Resultado de ida e volta: indisponível ({value['round_trip_reason']})")
    else:
        lines.append("Resultado líquido = recebimento da venda - desembolso da compra = "
                     f"{value['round_trip_result']} USDT")
    lines.extend(value["limitations"])
    return "\n".join(lines) + "\n"


def write_artifacts(directory, metadata, session, summary):
    target = Path(directory)
    # mkdir exclusivo também recusa symlink ou arquivo existente.
    target.mkdir(parents=True, exist_ok=False)
    marker = target / "INCOMPLETE"
    marker.write_text("Gravação incompleta: não consumir esta execução.\n", encoding="utf-8")
    # Manifesto é o último artefato; o marcador só some ao concluir tudo.
    contents = {"events.jsonl": "".join(canonical(e).decode("utf-8") + "\n" for e in session.events),
                "report.json": json_text(summary), "manifest.json": json_text(metadata)}
    for name, content in contents.items():
        temporary = target / (name + ".tmp")
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        temporary.replace(target / name)
    marker.unlink()
