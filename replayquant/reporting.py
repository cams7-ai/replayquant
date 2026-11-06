"""Relatórios, identidade por conteúdo e gravação sem sobrescrita."""
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import platform
from . import __version__
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
    return {"schema_version": 1, "run_id": sha256(canonical(identity)).hexdigest(),
            **identity, "code_files": code_files, "package_version": __version__,
            "dependencies": [], "decimal_policy": {"precision": 40, "rounding": "ROUND_HALF_EVEN",
                                                     "inexact": "ERROR"},
            "execution_model": "NEXT_OPEN_FULL_UNLIMITED_LIQUIDITY",
            "fee_rate": inputs.config.fee_rate, "slippage_rate": inputs.config.slippage_rate,
            "seed": None, "seed_reason": "NO_RANDOMNESS"}


@financial
def report(session):
    if not session.finished:
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
    if (len(fills) == 2 and fills[0].side == "BUY" and fills[1].side == "SELL"
            and fills[0].quantity == fills[1].quantity and session.balance.btc == 0):
        result = calculations[1]["cash_amount"] - calculations[0]["cash_amount"]
        reason = None
    incomplete = any(o.status in ("REJECTED", "UNEXECUTED") for o in session.orders)
    return {"schema_version": 1, "run_id": session.run_id,
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


def text_report(value):
    value = wire(value)
    lines = ["ReplayQuant — Sprint 06", f"Execução: {value['run_id']}",
             f"Caixa inicial: {value['initial_cash']} USDT"]
    for calc in value["calculations"]:
        lines.extend([f"{calc['side']} {calc['order_id']}: {calc['quantity']} BTC a {calc['price']} USDT/BTC",
                      f"  bruto = preço × quantidade = {calc['gross']} USDT",
                      f"  taxa = bruto × alíquota = {calc['fee']} USDT",
                      f"  {'Desembolso = bruto + taxa' if calc['side'] == 'BUY' else 'Recebimento = bruto - taxa'} = {calc['cash_amount']} USDT"])
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
