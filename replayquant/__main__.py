"""Interface local; erros técnicos nunca são resultados de política de ordens."""
import argparse
from decimal import Decimal
import sys
from .data import load_inputs
from .engine import replay
from .reporting import json_text, manifest, report, text_report, write_artifacts
from .validation import ValidationError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay didático de ordens Spot fictícias")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("demonstrar", "executar"):
        command = commands.add_parser(name, help="Exemplo manual" if name == "demonstrar" else "Replay de arquivos locais")
        command.add_argument("--formato", choices=("texto", "json"), default="texto")
        if name == "executar":
            command.add_argument("--dados", required=True)
            command.add_argument("--config", required=True)
            command.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    try:
        demonstration = args.command == "demonstrar"
        inputs = load_inputs("data/fixtures/sprint06-candles.json" if demonstration else args.dados,
                             "experiments/sprint06-manual.json" if demonstration else args.config)
        metadata = manifest(inputs)
        session = replay(inputs.candles, inputs.config, metadata["run_id"], inputs.diagnostics)
        summary = report(session)
        if demonstration:
            if not (summary["exit_code"] == 0 and len(session.fills) == 2
                    and session.balance.cash == Decimal("1000.799") and session.balance.btc == 0
                    and session.fees == Decimal("0.201")
                    and summary["round_trip_result"] == Decimal("0.799")):
                raise ValidationError("Demonstração divergiu dos resultados obrigatórios")
        else:
            write_artifacts(args.saida, metadata, session, summary)
        for event in session.events:
            if event["type"] in ("DIAGNOSTIC", "REJECTED", "UNEXECUTED"):
                print(f"Diagnóstico: {event.get('order_id', '')} {event.get('reason')}", file=sys.stderr)
        sys.stdout.write(json_text(summary) if args.formato == "json" else text_report(summary))
        return summary["exit_code"]
    except (ValidationError, OSError, UnicodeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    # Exceções inesperadas propagam com traceback e código não zero.


if __name__ == "__main__":
    sys.exit(main())
