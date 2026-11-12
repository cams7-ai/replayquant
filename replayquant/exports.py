"""Exportações determinísticas da análise, sem dependências de apresentação financeira."""
import csv
from io import StringIO
from html import escape
from .reporting import wire, canonical
from .ledger import PORTFOLIOS
from .validation import ValidationError

HEADERS = {
    'equity.csv': 'schema_version,run_id,portfolio,point_seq,at,source_event_seq,phase,cash_total,cash_available,cash_reserved,asset_quantity,mark_price,mark_at,mark_reason,cost_basis,realized_pnl,unrealized_pnl,gross_equity,hypothetical_liquidation_equity'.split(','),
    'trades.csv': 'schema_version,run_id,trade_id,lot_id,buy_execution_id,sell_execution_id,buy_at,sell_at,quantity,buy_price,sell_price,buy_gross,sell_gross,buy_fee,sell_fee,cash_outflow,cash_inflow,net_pnl,return_pct,return_numerator,return_denominator,duration_seconds,classification'.split(','),
    'metrics.csv': 'schema_version,run_id,scope,metric,value,unit,reason,numerator,denominator'.split(','),
    'benchmarks.csv': 'schema_version,run_id,portfolio,status,reason,observation_start,observed_until,initial_cash,final_cash,asset_quantity,paid_fees,gross_equity,hypothetical_liquidation_equity,return_pct,return_reason,hypothetical_return_pct,hypothetical_return_reason,time_in_position_seconds,time_in_position_pct'.split(','),
}
LABELS = {
    'realized_pnl': 'Resultado realizado', 'unrealized_pnl': 'Resultado não realizado bruto',
    'final_cash': 'Caixa final', 'final_asset_quantity': 'Posição final',
    'final_gross_equity': 'Patrimônio bruto marcado',
    'final_hypothetical_liquidation_equity': 'Liquidação hipotética líquida',
    'portfolio_return_pct': 'Retorno da carteira', 'hypothetical_liquidation_return_pct': 'Retorno hipotético de liquidação',
    'paid_fees': 'Taxas pagas', 'slippage_impact': 'Impacto de slippage',
    'attributed_execution_costs': 'Custos atribuídos à execução',
    'closed_trade_count': 'Operações encerradas', 'win_count': 'Ganhos', 'loss_count': 'Perdas',
    'break_even_count': 'Empates', 'win_rate_pct': 'Taxa de acerto', 'expectancy': 'Expectativa amostral',
    'max_drawdown_pct': 'Drawdown máximo percentual', 'max_drawdown_amount': 'Maior queda absoluta',
    'max_drawdown_duration_seconds': 'Maior duração observada de drawdown',
    'observation_duration_seconds': 'Duração do horizonte', 'time_in_position_seconds': 'Tempo em posição',
    'time_in_position_pct': 'Exposição temporal',
}
FORMULAS = [
    'Patrimônio bruto = caixa total + BTC × preço de marcação disponível.',
    'Patrimônio bruto = capital inicial + resultado realizado + resultado não realizado bruto.',
    'Base de custo = bruto da compra + taxa de compra; realizado = venda após taxa − base de custo.',
    'Não realizado bruto = BTC × marca − base de custo aberta.',
    'Retorno da carteira (%) = (patrimônio bruto final / capital inicial − 1) × 100.',
    'Retorno do trade (%) = lucro líquido / desembolso da compra × 100; o denominador difere do retorno da carteira.',
    'Liquidação hipotética = caixa + BTC × marca × (1 − slippage) × (1 − taxa); não gera execução ou cobrança.',
    'Drawdown (%) = (pico anterior − patrimônio) / pico anterior × 100; usa INITIAL, OPEN, FILL e CLOSE.',
    'Expectativa = soma dos lucros líquidos / operações encerradas; acerto = ganhos / operações encerradas × 100.',
    'Exposição (%) = segundos entre fills de entrada/saída (ou fim aceito) / segundos do horizonte × 100.',
    'Custos atribuídos = taxas pagas + impacto de slippage; não são debitados novamente.',
    'BUY_HOLD_BTC usa quantidade ideal = capital / (preço de compra × (1 + taxa)), piso no quantum 0.000000000001 BTC e caixa residual.',
    'KEEP_OPEN: posições abertas permanecem; liquidação é cenário hipotético, sem venda ou taxa fictícia.',
    'A amostra é fictícia e curta; sem anualização ou evidência de rentabilidade. USDT não é o próprio dólar.',
]


def metric_text(item):
    if item['value'] is None:
        return f"Indisponível ({item['reason']})"
    return f"{str(item['value']).replace('.', ',')} {item['unit']}"


def cell(value):
    return escape(str(value)).replace('|', r'\|').replace('\n', ' ')


def md_table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |']
                     + ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


def analysis_markdown(summary):
    value = wire(summary)
    a = value['analysis']
    lines = ['## Patrimônio e métricas', '', f"Estado: {value['status']} · Escopo: {a['scope']}", '',
             f"Horizonte UTC: {a['observation_start']} → {a['observed_until']}", '',
             md_table(['Métrica', 'Valor', 'Razão exata (na unidade exibida)'],
                      ((LABELS[k], metric_text(m), f"{m['numerator']}/{m['denominator']}" if m['numerator'] is not None else '—')
                       for k, m in sorted(a['metrics'].items()))), '', '## Referências comparáveis', '',
             'Cada referência usa capital independente, mesma cobertura e custos. Não somar as carteiras.', '',
             md_table(['Carteira', 'Estado', 'Patrimônio bruto (USDT)', 'Liquidação hipotética (USDT)', 'Retorno (%)', 'Taxas pagas USDT', 'Exposição %', 'Motivo'],
                      ((b['portfolio'], b['status'], b['metrics'].get('final_gross_equity', {}).get('value', '—'),
                        b['metrics'].get('final_hypothetical_liquidation_equity', {}).get('value', '—'),
                        b['metrics'].get('portfolio_return_pct', {}).get('value', '—'),
                        b['metrics'].get('paid_fees', {}).get('value', '—'), b['metrics'].get('time_in_position_pct', {}).get('value', '—'), b['reason'] or '—') for b in a['benchmarks'])),
             '', '## Memória de cálculo e reconciliação', '', f"Capital inicial: {value['initial_cash']} USDT.", '',
             f"Taxa fracionária: {a['execution_cost_policy']['fee_rate']}; slippage: {a['execution_cost_policy']['slippage_rate']}; quantidade: {a['execution_cost_policy']['strategy_quantity'] if value['schema_version'] not in (4, 5, 6) else 'variável por risco'} BTC.", '',
             f"Reconciliação: {a['reconciliation']['status']}; caixa reconstruído {a['reconciliation']['reconstructed_cash']} USDT; "
             f"BTC reconstruído {a['reconciliation']['reconstructed_asset']}.", '',
             md_table(['Ponto', 'UTC', 'Fase', 'Caixa USDT', 'BTC', 'Marca USDT/BTC', 'Base USDT', 'Realizado USDT', 'Não realizado USDT', 'Patrimônio USDT', 'Liquidação hipotética USDT'],
                      ((p['point_seq'], p['at'], p['phase'], p['cash_total'], p['asset_quantity'], p['mark_price'] if p['mark_price'] is not None else p['mark_reason'],
                        p['cost_basis'], p['realized_pnl'], p['unrealized_pnl'], p['gross_equity'], p['hypothetical_liquidation_equity']) for p in a['equity_curve'])),
             '', '## Operações encerradas', '',
             md_table(['Trade', 'Entrada UTC', 'Saída UTC', 'Desembolso USDT', 'Recebimento USDT', 'Taxas BUY/SELL USDT', 'Líquido USDT', 'Retorno', 'Duração s'],
                      ((t['trade_id'], t['buy_at'], t['sell_at'], t['cash_outflow'], t['cash_inflow'],
                        f"{t['buy_fee']} / {t['sell_fee']}", t['net_pnl'], metric_text(t['return_pct']), t['duration_seconds']) for t in a['closed_trades'])),
             '', '## Episódios de drawdown', '',
             md_table(['Pico UTC / ponto', 'Vale UTC / ponto', 'Queda USDT', 'Drawdown %', 'Recuperação UTC', 'Duração s', 'Motivo'],
                      ((f"{e['peak_at']} / {e['peak_point_seq']}", f"{e['trough_at']} / {e['trough_point_seq']}",
                        e['drawdown_amount'], e['drawdown_pct']['value'], e['recovery_at'] or '—', e['duration_seconds'], e['reason'] or 'RECOVERED') for e in a['drawdown_episodes'])), '',
             'Sem episódio: ' + (a['episode_reason'] or 'episódios registrados acima') + '.', '',
             '## Posição aberta e hipótese de liquidação', '']
    if a['open_position']:
        pos = a['open_position']
        lines.append(f"{pos['quantity']} BTC; base {pos['cost_basis']} USDT; não realizado {pos['unrealized_pnl']} USDT; "
                     f"taxa hipotética de saída {pos['hypothetical_exit_fee']} USDT; slippage hipotético {pos['hypothetical_exit_slippage']} USDT.")
    else:
        lines.append('Posição zerada. Nenhuma liquidação adicional foi simulada.')
    lines.extend(['', '## Parâmetros dos benchmarks', ''])
    for b in a['benchmarks']:
        lines.append(f"{b['portfolio']}: {cell(canonical(b['parameters']).decode('utf-8'))}")
        if b.get('open_position'):
            pos = b['open_position']
            lines.append(f"Base {pos['cost_basis']} USDT; taxa de saída hipotética {pos['hypothetical_exit_fee']} USDT (não paga).")
    lines.extend(['', '## Fórmulas e limites', ''] + [f'- {formula}' for formula in analysis_formulas(value)])
    return '\n'.join(lines) + '\n'


def markdown_report(summary):
    if summary['schema_version'] == 6:
        from .catalog_html import catalog_markdown
        return catalog_markdown(summary)
    if summary.get('schema_version') not in (3,4,5,6):
        raise ValidationError('Markdown exige --analise')
    if summary['schema_version'] in (4, 5, 6):
        from .risk_reporting import risk_markdown
        from .strategy_reporting import strategy_markdown
        strategy = strategy_markdown(summary) if summary['schema_version'] == 5 else ''
        sprint = '10' if summary['schema_version'] == 5 else '09'
        return f"# ReplayQuant — Sprint {sprint}\n\nExecução: {cell(summary['run_id'])}\n\n" + analysis_markdown(summary) + "\n" + strategy + risk_markdown(summary)
    return f"# ReplayQuant — Sprint 08\n\nExecução: {cell(summary['run_id'])}\n\n" + analysis_markdown(summary)


def csv_text(headers, rows):
    output = StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator='\n', extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow(wire(row))
    return output.getvalue()


def analysis_files(summary):
    a = summary['analysis']
    def write_csv(headers, rows):
        if summary['schema_version'] == 6:
            identity = {k: summary[k] for k in ('source', 'symbol', 'base_asset', 'quote_asset', 'interval')}
            return csv_text(headers + list(identity), ({**row, **identity} for row in rows))
        return csv_text(headers, rows)
    base = dict(schema_version=summary['schema_version'], run_id=summary['run_id'])
    ledgers = list(a['ledger_entries'])
    curves = list(a['equity_curve'])
    benchmark_rows = []
    for b in a['benchmarks']:
        ledgers.extend(b['ledger_entries'])
        curves.extend(b['equity_curve'])
        m = b['metrics']
        get = lambda key, field='value': m.get(key, {}).get(field)
        benchmark_rows.append({**base, **{k: b[k] for k in ('portfolio', 'status', 'reason', 'observation_start', 'observed_until', 'initial_cash')},
                               'final_cash': get('final_cash'), 'asset_quantity': get('final_asset_quantity'),
                               'paid_fees': get('paid_fees'), 'gross_equity': get('final_gross_equity'),
                               'hypothetical_liquidation_equity': get('final_hypothetical_liquidation_equity'),
                               'return_pct': get('portfolio_return_pct'), 'return_reason': get('portfolio_return_pct', 'reason') or b['reason'],
                               'hypothetical_return_pct': get('hypothetical_liquidation_return_pct'),
                               'hypothetical_return_reason': get('hypothetical_liquidation_return_pct', 'reason') or b['reason'],
                               'time_in_position_seconds': get('time_in_position_seconds'), 'time_in_position_pct': get('time_in_position_pct')})
    ledgers = wire(ledgers)
    if summary['schema_version'] == 5:
        ledgers = [{**row, 'schema_version': 5} for row in ledgers]
    ledgers.sort(key=lambda e: (e['at'], e['source_event_seq'], PORTFOLIOS.index(e['portfolio']), e['ledger_seq']))
    trades = [{**base, **t, 'return_pct': t['return_pct']['value'],
               'return_numerator': t['return_pct']['numerator'], 'return_denominator': t['return_pct']['denominator']} for t in a['closed_trades']]
    metrics = [{**base, 'scope': a['scope'], 'metric': name, **value} for name, value in sorted(a['metrics'].items())]
    files = {'ledger.jsonl': ''.join(canonical(e).decode('utf-8') + '\n' for e in ledgers),
            'equity.csv': write_csv(HEADERS['equity.csv'] + (['asset_available','asset_reserved'] if summary['schema_version'] in (4, 5, 6) else []), curves),
            'trades.csv': write_csv(HEADERS['trades.csv'], trades),
            'metrics.csv': write_csv(HEADERS['metrics.csv'], metrics),
            'benchmarks.csv': write_csv(HEADERS['benchmarks.csv'], benchmark_rows),
            'report.md': markdown_report(summary)}

    if summary['schema_version'] in (4, 5, 6):
        files['risk.jsonl'] = ''.join(canonical(r).decode('utf-8')+'\n' for r in summary['risk']['records'])
        files['reservations.jsonl'] = ''.join(canonical(r).decode('utf-8')+'\n' for r in summary['risk']['reservations'])
    return files


def analysis_formulas(summary):
    if summary['schema_version'] == 6:
        base = summary['base_asset']
        return [line.replace('piso no quantum 0.000000000001 BTC', 'piso no step fictício configurado').replace('BUY_HOLD_BTC', 'BUY_HOLD_ASSET').replace('BTC', base) for line in FORMULAS]
    if summary['schema_version'] in (4, 5, 6):
        return [line.replace('piso no quantum 0.000000000001 BTC', 'piso no step fictício configurado') for line in FORMULAS]
    return FORMULAS
