"""Relatório schema 6 com unidades resolvidas do instrumento."""
from html import escape
from .reporting import wire, canonical
from .html_chart import candle_chart
from .html_analysis import analysis_html
from .strategy_reporting import strategy_html, strategy_markdown
from .risk_reporting import risk_html, risk_markdown


def metadata_rows(value):
    instrument = value['instrument']
    coverage = value['coverage']
    filters = instrument['instrument_filters']
    rows = [
        ('Origem', value['source']), ('Par', value['symbol']),
        ('Moeda base', value['base_asset']), ('Moeda de cotação', value['quote_asset']),
        ('Intervalo', value['interval']), ('Hipótese das regras', instrument['rules_basis']),
        ('Referência das regras UTC', instrument['rules_as_of']),
        ('Origem das regras', instrument['rules_source']),
        ('Step / quantidade mínima', f"{filters['step']} / {filters['min_quantity']} {value['base_asset']}"),
        ('Nocional mínimo', f"{filters['min_notional']} USDT"),
        ('Disponibilidade UTC', f"{instrument['available_from']} → {instrument['available_until'] or 'sem fim definido'}"),
        ('Janela solicitada UTC', f"{value['window']['start']} → {value['window']['end']}"),
        ('Cobertura solicitada', f"{coverage['status']} · {coverage['accepted_candles']}/{coverage['expected_candles']} candles"),
        ('Cobertura elegível', f"{coverage['accepted_candles']}/{coverage['expected_eligible_candles']} candles"),
        ('Exclusões', canonical(coverage['excluded']).decode()),
        ('Motivos de cobertura', ', '.join(coverage['reasons']) or '—'),
        ('Duplicatas / lacunas', f"{coverage['duplicates']} / {len(coverage['gaps'])}"),
        ('Último fechamento aceito UTC', coverage['observed_until'] or 'nenhum'),
    ]

    for p in value.get('provenance', []):
        rows.extend([('Origem histórica', p['source']),('dataset_version',p['dataset_version']),
                     ('ingestion_id',p['ingestion_id']),('Qualidade',p['quality_status']),
                     ('Universo',p['universe']['basis']),('Restrição',p['universe']['restriction']),
                     ('Disponibilidade da informação',p['policy'])])
    return rows


def catalog_markdown(value):
    from .exports import md_table, metric_text
    value = wire(value)
    a = value['analysis']
    return '\n'.join([
        '# ReplayQuant — Sprint 11', '', f"Execução {value['run_id']}", '',
        f"{value['symbol']} · {value['status']} · código {value['exit_code']}", '',
        md_table(('Metadado', 'Valor'), metadata_rows(value)), '',
        md_table(('Métrica', 'Valor'), ((key, metric_text(item)) for key,item in a['metrics'].items())), '',
        md_table(('Carteira', 'Estado', 'Patrimônio USDT', 'Motivo'),
                 ((b['portfolio'], b['status'], b['metrics'].get('final_gross_equity',{}).get('value'), b['reason']) for b in a['benchmarks'])), '',
        md_table(('Ordem', 'Estado', 'Motivo'),
                 ((o['request']['id'], o['status'], o['reason']) for o in value['orders'])), '',
        md_table(('Lado', f"Quantidade {value['base_asset']}", f"Preço USDT/{value['base_asset']}", 'Taxa USDT', 'Bruto USDT', 'Fluxo USDT'),
                 ((c['side'], c['quantity'], c['price'], c['fee'], c['gross'], c['cash_amount']) for c in value['calculations'])), '',
        md_table(('Trade', 'Compra UTC', 'Venda UTC', 'Líquido USDT'),
                 ((t['trade_id'], t['buy_at'], t['sell_at'], t['net_pnl']) for t in a['closed_trades'])), '',
        strategy_markdown(value), risk_markdown(value),
    ]) + '\n'


def catalog_html(value):
    from .html_report import CSS, table
    value = wire(value)
    base = value['base_asset']
    metadata = table(('Metadado', 'Valor'), metadata_rows(value), 'Instrumento, hipótese das regras e cobertura')
    parts = ['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>ReplayQuant — Sprint 11</title><style>'+CSS+'.catalog-panel table{table-layout:fixed}.catalog-panel th:first-child,.catalog-panel td:first-child{width:30%}</style></head><body><main>',
             '<header><h1>ReplayQuant — Sprint 11</h1>',
             f"<p>{escape(value['symbol'])} · {escape(value['status'])} · código {value['exit_code']}</p>",
             '<p class="identity">'+escape(value['run_id'])+'</p></header>',
             '<nav><a href="#instrumento">Instrumento</a><a href="#grafico">Candles</a>'
             '<a href="#estrategia">Estratégia</a><a href="#analise">Patrimônio</a><a href="#risco">Risco</a></nav>',
             '<section class="panel catalog-panel" id="instrumento"><h2>Instrumento e cobertura</h2>', metadata,
             f"<p>Caixa final {escape(value['final_balance']['cash'])} USDT · Posição {escape(value['final_balance']['asset_quantity'])} {base}</p></section>",
             candle_chart(value), analysis_html(value, library_loaded=bool(value['candles'])),
             strategy_html(value),
             '<section class="panel"><h2>Ordens e cálculos</h2>',
             table(('Ordem', 'Estado', 'Motivo'),
                   ((o['request']['id'], o['status'], o['reason']) for o in value['orders']), 'Estados finais'),
             table(('UTC', 'Lado', f'Quantidade {base}', f'Preço USDT/{base}', 'Taxa USDT'),
                   ((f['at'], f['side'], f['quantity'], f['price'], f['fee']) for f in value['fills']), 'Preenchimentos elegíveis'),
             table(('Lado', 'Bruto USDT', 'Taxa USDT', 'Fluxo USDT'),
                   ((c['side'], c['gross'], c['fee'], c['cash_amount']) for c in value['calculations']),
                   'Bruto = quantidade × preço; compra soma taxa, venda desconta taxa'), '</section>',
             risk_html(value), '</main></body></html>']
    return ''.join(parts)
