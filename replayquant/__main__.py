"""Interface local; erros técnicos nunca são resultados de política de ordens."""
import argparse
from decimal import Decimal
import sys
from .data import load_inputs
from .engine import replay
from .html_report import html_report
from .reporting import json_text, manifest, report, text_report, write_artifacts
from .validation import ValidationError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay didático de ordens Spot fictícias")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("demonstrar", "executar"):
        command = commands.add_parser(name, help="Exemplo manual ou SMA" if name == "demonstrar" else "Replay de arquivos locais")
        command.add_argument("--formato", choices=("texto", "json", "html"), default="texto",
                             help="Formato de stdout: texto (padrão), JSON ou HTML independente")
        if name == "demonstrar":
            command.add_argument("--estrategia", choices=("sma",), help="Demonstração SMA da Sprint 07")
        if name == "executar":
            command.add_argument("--dados", required=True)
            command.add_argument("--config", required=True)
            command.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    try:
        demonstration = args.command == "demonstrar"
        sma_demo = demonstration and args.estrategia == "sma"
        demo_data = "data/fixtures/sprint07-candles.json" if sma_demo else "data/fixtures/sprint06-candles.json"
        demo_config = "experiments/sprint07-sma.json" if sma_demo else "experiments/sprint06-manual.json"
        inputs = load_inputs(demo_data if demonstration else args.dados,
                             demo_config if demonstration else args.config)
        metadata = manifest(inputs)
        session = replay(inputs.candles, inputs.config, metadata["run_id"], inputs.diagnostics)
        summary = report(session)
        if sma_demo:
            if not (summary["exit_code"] == 0 and len(summary["evaluations"]) == 8
                    and len(summary["signals"]) == len(summary["decisions"]) == 2
                    and all(d["approved"] for d in summary["decisions"])
                    and len(session.orders) == len(session.fills) == 2
                    and session.balance.cash == Decimal("999.6") and session.balance.btc == 0
                    and session.fees == Decimal("0.2")
                    and summary["round_trip_result"] == Decimal("-0.4")):
                raise ValidationError("Demonstração SMA divergiu dos resultados obrigatórios")
        elif demonstration:
            if not (summary["exit_code"] == 0 and len(session.fills) == 2
                    and session.balance.cash == Decimal("1000.799") and session.balance.btc == 0
                    and session.fees == Decimal("0.201")
                    and summary["round_trip_result"] == Decimal("0.799")):
                raise ValidationError("Demonstração divergiu dos resultados obrigatórios")
        else:
            write_artifacts(args.saida, metadata, session, summary)
        for event in session.events:
            if event["type"] in ("DIAGNOSTIC", "REJECTED", "UNEXECUTED", "INTERRUPTED"):
                print(f"Diagnóstico: {event.get('order_id', '')} {event.get('reason')}", file=sys.stderr)
            elif event["type"] == "DECISION" and not event["approved"]:
                print(f"Diagnóstico: {event['signal_id']} {event['reason']}", file=sys.stderr)
        render = {"texto": text_report, "json": json_text, "html": html_report}
        sys.stdout.write(render[args.formato](summary))
        return summary["exit_code"]
    except (ValidationError, OSError, UnicodeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    # Exceções inesperadas propagam com traceback e código não zero.


if __name__ == "__main__":
    sys.exit(main())
