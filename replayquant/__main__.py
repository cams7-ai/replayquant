"""Interface local; erros técnicos nunca são resultados de política de ordens."""
import argparse
from decimal import Decimal
import sys
from .data import load_inputs
from .engine import replay
from .html_report import html_report
from .reporting import json_text, manifest, report, text_report, write_artifacts
from .validation import ValidationError
from .risk_models import RiskConfig
from .exports import markdown_report


def check_manual_analysis(summary):
    a = summary['analysis']
    expected = {'portfolio_return_pct': '0.079900000000', 'max_drawdown_pct': '0.010090918174',
                'time_in_position_pct': '33.333333333333', 'max_drawdown_duration_seconds': '60',
                'time_in_position_seconds': '60', 'closed_trade_count': '1', 'win_count': '1'}
    if any(Decimal(str(a['metrics'][key]['value'])) != Decimal(value) for key, value in expected.items()):
        raise ValidationError('Métricas da demonstração divergentes')
    hold = a['benchmarks'][1]
    if (hold['metrics']['final_gross_equity']['value'] != Decimal('1008.991008991')
            or hold['metrics']['final_hypothetical_liquidation_equity']['value'] != Decimal('1007.98201798201')
            or len(a['ledger_entries']) != 3):
        raise ValidationError('Ledger/benchmark da demonstração divergentes')


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay didático de ordens Spot fictícias")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("demonstrar", "executar"):
        command = commands.add_parser(name, help="Exemplo manual ou SMA" if name == "demonstrar" else "Replay de arquivos locais")
        command.add_argument("--formato", choices=("texto", "json", "html", "markdown"), default="texto",
                             help="Formato de stdout: texto (padrão), JSON, HTML ou Markdown com --analise")
        command.add_argument("--analise", action="store_true", help="Ledger, patrimônio, métricas e referências (Sprint 08)")
        if name == "demonstrar":
            command.add_argument("--risco", action="store_true", help="Demonstração de risco e proteção (Sprint 09)")
            command.add_argument("--estrategia", choices=("sma",), help="Demonstração SMA da Sprint 07")
        if name == "executar":
            command.add_argument("--dados", required=True)
            command.add_argument("--config", required=True)
            command.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    if args.command == "demonstrar" and args.formato == "markdown" and not args.analise and not args.risco:
        parser.error("--formato markdown exige --analise")
    try:
        demonstration = args.command == "demonstrar"
        sma_demo = demonstration and args.estrategia == "sma"
        risk_demo = demonstration and args.risco
        demo_data = "data/fixtures/sprint07-candles.json" if sma_demo else "data/fixtures/sprint06-candles.json"
        demo_config = "experiments/sprint07-sma.json" if sma_demo else "experiments/sprint06-manual.json"
        if risk_demo:
            demo_config = 'experiments/sprint09-sma.json' if sma_demo else 'experiments/sprint09-manual.json'
            demo_data = 'data/fixtures/sprint07-candles.json' if sma_demo else 'data/fixtures/sprint09-candles.json'
        inputs = load_inputs(demo_data if demonstration else args.dados,
                             demo_config if demonstration else args.config)
        enabled = args.analise or isinstance(inputs.config, RiskConfig)
        if args.formato == 'markdown' and not enabled:
            parser.error('--formato markdown exige --analise ou configuração de risco')
        metadata = manifest(inputs, analysis=enabled)
        session = replay(inputs.candles, inputs.config, metadata["run_id"], inputs.diagnostics)
        summary = report(session, analysis=enabled)
        if risk_demo:
            if sma_demo:
                valid = (len(summary['evaluations']) == 8 and len(summary['signals']) == 2
                         and len(session.fills) == 2 and session.fills[0].quantity == Decimal('0.000962')
                         and session.balance.cash == Decimal('999.8076') and session.balance.btc == 0
                         and session.fees == Decimal('0.1924') and summary['exit_code'] == 0)
            else:
                valid = (summary['exit_code'] == 0 and len(session.fills) == 2
                         and session.balance.cash == Decimal('990.00361') and session.balance.btc == 0
                         and session.fees == Decimal('0.18639')
                         and summary['analysis']['metrics']['realized_pnl']['value'] == Decimal('-9.99639'))
            if not valid:
                raise ValidationError('Demonstração de risco divergiu dos resultados obrigatórios')
        elif sma_demo:
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
        if demonstration and args.analise and not risk_demo:
            metrics = summary['analysis']['metrics']
            expected = Decimal('-0.4') if sma_demo else Decimal('0.799')
            expected_points = 8*2+2+1 if sma_demo else 9
            if metrics['realized_pnl']['value'] != expected or len(summary['analysis']['equity_curve']) != expected_points:
                raise ValidationError('Análise da demonstração divergiu dos resultados obrigatórios')
            if not sma_demo:
                check_manual_analysis(summary)
            else:
                fills = [p for p in summary['analysis']['equity_curve'] if p['phase'] == 'FILL']
                if (fills[0]['gross_equity'] != Decimal('999.7999')
                        or metrics['slippage_impact']['value'] != Decimal('0.2')):
                    raise ValidationError('Marcação/custos da demonstração SMA divergentes')
        render = {"texto": text_report, "json": json_text, "html": html_report, "markdown": markdown_report}
        sys.stdout.write(render[args.formato](summary))
        return summary["exit_code"]
    except (ValidationError, OSError, UnicodeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    # Exceções inesperadas propagam com traceback e código não zero.


if __name__ == "__main__":
    sys.exit(main())
