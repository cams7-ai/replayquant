"""Relatório HTML independente, com valores exatos e estilo para impressão."""
from html import escape
from fractions import Fraction

from .html_analysis import analysis_html
from .html_chart import candle_chart, outcome, closed_trades, exact_text

from .reporting import wire, ratio_text


CSS = """
:root{color-scheme:light;--ink:#172c3e;--muted:#546779;--line:#dbe4ea;--accent:#087e83}
*{box-sizing:border-box}body{margin:0;background:#f2f5f7;color:var(--ink);font:15px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:44px 28px}header{border-top:5px solid var(--accent);padding:28px 0}
.eyebrow{font-size:12px;font-weight:750;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
h1{font-size:38px;letter-spacing:-.04em;line-height:1.15;margin:12px 0}h2{font-size:24px;margin:0 0 16px}
h3{font-size:18px;margin:0 0 12px}p{margin:8px 0;overflow-wrap:anywhere}.muted,small{color:var(--muted)}
.identity{overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:24px 0}
.kpi,.panel{background:white;border:1px solid var(--line);border-radius:10px;padding:22px}
.kpi span{display:block;font-size:12px;color:var(--muted)}.kpi strong{display:block;font-size:22px;overflow-wrap:anywhere}
.panel{margin:22px 0}.badge{display:inline-block;font-size:12px;font-weight:750;padding:5px 12px;border-radius:20px}
.approved{background:#e0f4ed;color:#146347}.attention{background:#fff0d3;color:#815900}
nav{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}a{color:var(--accent)}nav a{padding:7px 14px;border:1px solid var(--line);border-radius:6px;text-decoration:none;background:white}
.table-wrap{overflow-x:auto}.table-wrap table{width:100%;border-collapse:collapse;font-size:13px}caption{text-align:left;color:var(--muted);margin-bottom:12px}
.table-wrap th,.table-wrap td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:anywhere}
.table-wrap th{color:var(--muted);font-weight:600}.table-wrap td{font-variant-numeric:tabular-nums}
.note{border-left:3px solid var(--accent);background:#f1f8f8;padding:14px 18px;margin-top:18px}
.calculation{padding:18px 0;border-top:1px solid var(--line)}.formula{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
.gain{color:#14794e}.loss{color:#bd2636}.neutral{color:#546779}.buy{color:#2563eb}
.candle-chart{width:100%;height:470px;min-width:0}
.chart-controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.chart-controls[hidden]{display:none}
.chart-controls button,.equity-fit{border:1px solid var(--line);background:#fff;border-radius:6px;padding:7px 12px;color:var(--accent);cursor:pointer;font:inherit}
.chart-controls button:hover,.chart-controls button:focus-visible,.equity-fit:hover,.equity-fit:focus-visible{background:#e8f5f5;outline:2px solid var(--accent);outline-offset:1px}
.chart-axis-title,.chart-attribution{font-size:12px;color:var(--muted)}
.chart-readout{font:12px/1.6 ui-monospace,monospace;white-space:pre-line;min-height:42px;overflow-wrap:anywhere}
.chart-licenses{font-size:12px;color:var(--muted)}.chart-licenses pre{white-space:pre-wrap;overflow-wrap:anywhere}
.chart-print-image{display:none}
.chart-legend{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;font-weight:650;margin:14px 0}
.trade-result{border-left:3px solid currentColor;padding:10px 14px;background:#f8fafc;overflow-wrap:anywhere}
@media print{.candle-chart,.chart-controls,.chart-readout,#chart-help,.chart-licenses{display:none!important}.chart-print-image{display:block;width:100%;height:auto}}

.risk-panel .table-wrap table{min-width:1200px}
.risk-panel .table-wrap td{white-space:nowrap;overflow-wrap:normal}
.risk-panel h3{margin-top:22px}
.strategy-panel .table-wrap table{min-width:1200px}
.strategy-panel .table-wrap th,.strategy-panel .table-wrap td{white-space:nowrap;overflow-wrap:normal}
@media print{.strategy-panel .table-wrap table{min-width:0;table-layout:fixed}.strategy-panel .table-wrap th,.strategy-panel .table-wrap td{white-space:normal;overflow-wrap:anywhere}}
@media print{.risk-panel .table-wrap table{min-width:0;table-layout:fixed}.risk-panel .table-wrap td{white-space:normal;overflow-wrap:anywhere}}
.equity-chart{height:300px;width:100%;min-width:0}.equity-panel{margin:24px 0}.equity-print{display:none}
@media print{.equity-chart,.equity-readout,.equity-fit{display:none!important}.equity-print{display:block;width:100%;height:auto}.equity-print:not([src]){display:none}}
footer{border-top:1px solid var(--line);padding-top:20px;font-size:12px;color:var(--muted)}
@media(max-width:720px){main{padding:24px 16px}h1{font-size:30px}.panel{padding:16px}.table-wrap table{min-width:680px}}
@media print{@page{size:A4 landscape;margin:14mm}body{background:white;font-size:11px}main{max-width:none;padding:0}nav{display:none}h1{font-size:28px}.panel{border-radius:0;padding:16px}.table-wrap{overflow:visible}.table-wrap table{font-size:10px;min-width:0}.table-wrap tr,.kpi,.calculation{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit;text-decoration:none}}
"""

SIDES = {"BUY": "Compra", "SELL": "Venda"}
STATUSES = {"NEW": "Aceita", "FILLED": "Preenchida", "REJECTED": "Rejeitada",
            "UNEXECUTED": "Não executada"}


def safe(value):
    return escape(str(value))


def number(value, unit):
    # Apenas apresentação: não converte para float nem arredonda os decimais.
    return f"{safe(value).replace('.', ',')} {safe(unit)}"


def table(headers, rows, caption):
    head = ''.join(f'<th scope="col">{safe(label)}</th>' for label in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{safe(cell)}</td>' for cell in row) + '</tr>'
                   for row in rows)
    return (f'<div class="table-wrap"><table><caption>{safe(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def html_report(value):
    if value['schema_version'] == 6:
        from .catalog_html import catalog_html
        return catalog_html(value)
    value = wire(value)
    balance = value["final_balance"]
    complete = value["exit_code"] == 0
    risk = value["schema_version"] in (4, 5)
    modular = value["schema_version"] == 5
    enriched = value["schema_version"] in (3,4,5)
    sma = value["schema_version"] == 2 or value.get("simulation_mode") == "SMA"
    interrupted = value.get("status") == "INTERRUPTED"
    state = ("Replay interrompido — relatório parcial" if interrupted else
             ("Replay concluído" if complete else "Replay concluído com bloqueios ou ordens rejeitadas ou não executadas"))
    result = value["round_trip_result"]
    trades = closed_trades(value) if sma else []
    multiple_closed = len(trades) > 1
    display_result = sum((t['net'] for t in trades), Fraction()) if multiple_closed else result
    result_class = outcome(Fraction(display_result)) if sma and display_result is not None else ''
    result_heading = 'Resultado líquido das operações encerradas' if multiple_closed else 'Resultado líquido da ida e volta'
    if enriched:
        display_result = value['analysis']['metrics']['realized_pnl']['value']
        result_class = outcome(Fraction(display_result))
        result_heading = 'Resultado realizado das operações encerradas'
    parts = ['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>ReplayQuant | Relatório de replay Spot</title>',
             f'<style>{CSS}</style></head><body><main>',
             f'<header><div class="eyebrow">ReplayQuant / Sprint {"10" if modular else ("09" if risk else ("08" if enriched else ("07" if sma else "06")))}</div>',
             '<h1>Relatório de replay Spot</h1>',
             '<p class="muted">Ordens, preenchimentos e memória de cálculo de BTC/USDT.</p>',
             f'<p class="muted">Dados fictícios · {safe(value["strategy"]["name"]) if modular else ("Estratégia SMA" if sma else "Ordens manuais")} · Horários em UTC</p>',
             f'<p class="identity">Execução: {safe(value["run_id"])}</p>',
             f'<span class="badge {"approved" if complete else "attention"}">'
             f'{safe(state)}</span>',
             f'<p class="muted">Código de saída: {safe(value["exit_code"])}</p></header>',
             '<nav aria-label="Seções do relatório"><a href="#resumo">Resumo</a>'
             + ('<a href="#grafico">Gráfico</a>' if sma or modular else '')
             + ('<a href="#analise">Patrimônio e métricas</a>' if enriched else '')
             + '<a href="#ordens">Ordens</a><a href="#execucoes">Preenchimentos</a>'
             '<a href="#calculos">Memória de cálculo</a><a href="#limites">Limitações</a></nav>',
             '<section id="resumo"><h2>Resumo financeiro</h2><div class="kpis">']
    for label, amount, unit in (
        ("Caixa inicial", value["initial_cash"], "USDT"),
        ("Caixa final", balance["cash"], "USDT"),
        ("Posição final", balance["btc"], "BTC"),
        ("Taxas totais", value["total_fees"], "USDT"),
    ):
        parts.append(f'<div class="kpi"><span>{label}</span><strong>{number(amount, unit)}</strong></div>')
    parts.append(f'</div><aside class="note"><strong class="{result_class}">{result_heading}</strong>')
    if display_result is None:
        parts.append(f'<p>Indisponível ({safe(value["round_trip_reason"])}). '
                     'Exige exatamente uma compra seguida de uma venda integral e posição final zero.</p>')
    else:
        displayed = exact_text(display_result) if multiple_closed else display_result
        explanation = ('Soma dos resultados realizados, com taxas de compra e venda; '
                       'posições abertas não entram nesse valor.' if multiple_closed else
                       'Recebimento da venda − desembolso da compra.')
        parts.append(f'<p class="{result_class}">{number(displayed, "USDT")}</p><p>{explanation}</p>')
    parts.append('<p>Os saldos e custos descrevem a mecânica do replay; não avaliam uma estratégia. ' +
                 ('Posições abertas são marcadas a mercado; a liquidação permanece hipotética.' if enriched else
                  'Posições abertas não são marcadas a mercado nem liquidadas automaticamente.') + '</p></aside></section>')
    if sma or risk:
        parts.append(candle_chart(value))
    if enriched:
        parts.append(analysis_html(value, library_loaded=(sma or risk) and bool(value.get("candles"))))
    if modular:
        from .strategy_reporting import strategy_html
        parts.append(strategy_html(value))
    if sma:
        parts.append('<section class="panel"><h2>Estratégia SMA e causalidade</h2>')
        parts.append(f'<p>Estado: {safe(value["status"])} · Pendência: {safe(value["pending_order_id"] or "nenhuma")}</p>')
        if value["diagnostic"]:
            parts.append(f'<p>Diagnóstico: {safe(value["diagnostic"])}</p>')
        parts.append('<h3>Avaliações</h3>')
        parts.append(table(("Avaliação / seq", "Horário UTC", "SMA curta", "SMA longa", "Anterior / atual", "Resultado"),
                           ((f"{e['evaluation_id']} / {e['seq']}", e["at"], ratio_text(e["short"]),
                             ratio_text(e["long"]), f"{e['previous_comparison']} / {e['comparison']}",
                             e["side"] or e["reason"]) for e in value["evaluations"]),
                           "Razões exatas em USDT/BTC; comparação -1, 0 ou 1; indisponível no aquecimento"))
        parts.append('<h3>Sinais</h3>')
        parts.append(table(("Sinal", "Avaliação", "Horário UTC", "Lado"),
                           ((e["signal_id"], e["evaluation_id"], e["at"], e["side"]) for e in value["signals"]),
                           "Cruzamentos matemáticos"))
        parts.append('<h3>Decisões</h3>')
        parts.append(table(("Decisão", "Sinal", "Resultado", "Ordem"),
                           ((e["decision_id"], e["signal_id"], "Aprovada" if e["approved"] else e["reason"],
                             e["order_id"] or "Nenhuma") for e in value["decisions"]), "Política de entrada e saída"))
        parts.append('<h3>Intenções</h3>')
        parts.append(table(("Intenção", "Decisão", "Ordem"),
                           ((e["intent_id"], e["decision_id"], e["order_id"]) for e in value["intentions"]),
                           "Intenções aprovadas; saldos mudam somente no preenchimento"))
        parts.append('</section>')
    parts.append(f'<section class="panel" id="ordens"><h2>{"Ordens da estratégia" if modular else ("Ordens SMA" if sma else "Ordens manuais")}</h2>')
    if value["orders"]:
        parts.append(table(("Ordem", "Submissão (UTC)", "Lado", "Estado", "Motivo"), (
            (o["request"]["id"], o["request"]["at_close"], SIDES.get(o["request"]["side"], o["request"]["side"]),
             STATUSES.get(o["status"], o["status"]) + f' ({o["status"]})', o["reason"] or "Sem rejeição")
            for o in value["orders"]), "Solicitações e estados finais"))
    else:
        parts.append('<p>Nenhuma ordem solicitada.</p>')
    parts.append('</section><section class="panel" id="execucoes"><h2>Preenchimentos</h2>')
    if value["fills"]:
        parts.append(table(("Execução / ordem", "Horário (UTC)", "Lado", "Quantidade (BTC)",
                            "Preço (USDT/BTC)", "Taxa (USDT)"), (
            (f'{f["id"]} / {f["order_id"]}', f["at"], SIDES.get(f["side"], f["side"]),
             f["quantity"].replace('.', ','), f["price"].replace('.', ','), f["fee"].replace('.', ','))
            for f in value["fills"]), "Execuções efetivas na abertura seguinte"))
    else:
        parts.append('<p>Nenhum preenchimento realizado.</p>')
    parts.append('</section><section class="panel" id="calculos"><h2>Memória de cálculo</h2>'
                 '<p class="muted">Valores decimais exatos; taxas e fluxos de caixa em USDT.</p>')
    for calc in value["calculations"]:
        if sma:
            parts.append(f'<p>Preço de referência: {number(calc["reference_price"], "USDT/BTC")} · '
                         f'Preço efetivo: {number(calc["effective_price"], "USDT/BTC")} · '
                         f'Slippage: {safe(calc["slippage_rate"])} · Alíquota: {safe(calc["fee_rate"])}</p>')
        buy = calc["side"] == "BUY"
        parts.append(f'<article class="calculation"><h3>{safe(SIDES.get(calc["side"], calc["side"]))}'
                     f' · {safe(calc["order_id"])}</h3>'
                     f'<p>Bruto = preço × quantidade</p><p class="formula">{number(calc["price"], "USDT/BTC")}'
                     f' × {number(calc["quantity"], "BTC")} = {number(calc["gross"], "USDT")}</p>'
                     f'<p>Taxa = bruto × alíquota = {number(calc["fee"], "USDT")}</p>'
                     f'<p>{"Desembolso = bruto + taxa" if buy else "Recebimento = bruto − taxa"}</p>'
                     f'<p class="formula">{number(calc["gross"], "USDT")} {"+" if buy else "−"} '
                     f'{number(calc["fee"], "USDT")} = {number(calc["cash_amount"], "USDT")}</p></article>')
    if not value["calculations"]:
        parts.append('<p>Sem preenchimentos, não há custos de execução a calcular.</p>')
    if result is not None:
        buy, sell = value["calculations"]
        parts.append(f'<aside class="note"><p>Resultado líquido = recebimento da venda − desembolso da compra</p>'
                     f'<p class="formula">{number(sell["cash_amount"], "USDT")} − '
                     f'{number(buy["cash_amount"], "USDT")} = {number(result, "USDT")}</p></aside>')
    if risk:
        from .risk_reporting import risk_html
        parts.append(risk_html(value))
    parts.append('</section><section class="panel" id="limites"><h2>Premissas e limitações</h2><ul>')
    parts.extend(f'<li>{safe(item)}</li>' for item in value["limitations"])
    parts.append('</ul></section><footer>ReplayQuant · Relatório local e independente de conexão à internet. '
                 'Para imprimir ou salvar em PDF, use a opção Imprimir do navegador.</footer></main></body></html>\n')
    return ''.join(parts)
