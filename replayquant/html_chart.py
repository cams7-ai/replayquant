"""Lightweight Charts offline; valores financeiros exatos fora da renderização JS."""
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from html import escape
import json
from pathlib import Path


def exact_text(value):
    """Representa uma razão decimal finita sem contexto Decimal ou float."""
    value = Fraction(value)
    numerator, denominator = value.numerator, value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        return f"{numerator}/{value.denominator}"
    places = max(twos, fives)
    scaled = abs(numerator) * 2 ** (places - twos) * 5 ** (places - fives)
    digits = str(scaled).zfill(places + 1)
    text = (digits[:-places] + ',' + digits[-places:]).rstrip('0').rstrip(',') if places else digits
    return ('−' if numerator < 0 else '') + text


def outcome(value):
    return 'gain' if value > 0 else ('loss' if value < 0 else 'neutral')


def closed_trades(value):
    """Idas e voltas efetivamente preenchidas, sem avaliar posição aberta."""
    purchase = None
    trades = []
    calculations = {c['order_id']: c for c in value['calculations']}
    for fill in value['fills']:
        if fill['side'] == 'BUY':
            purchase = fill
        elif purchase is not None:
            buy = calculations[purchase['order_id']]
            sell = calculations[fill['order_id']]
            net = Fraction(sell['cash_amount']) - Fraction(buy['cash_amount'])
            fees = Fraction(buy['fee']) + Fraction(sell['fee'])
            trades.append(dict(buy=purchase, sell=fill, net=net, fees=fees))
            purchase = None
    return trades


ASSETS = Path(__file__).resolve().parent / 'assets'
LIBRARY = 'lightweight-charts-5.2.0.standalone.production.js'


def unix_time(value):
    return (datetime.fromisoformat(value) - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(seconds=1)


def chart_data(value):
    """Strings exatas até a fronteira JS; inclui somente candles já processados."""
    trades = closed_trades(value)
    results = {t['sell']['id']: t for t in trades}
    executions = []
    for fill in value['fills']:
        trade = results.get(fill['id'])
        executions.append({**fill, 'time': unix_time(fill['at']),
                           'classification': 'buy' if fill['side'] == 'BUY' else
                           (outcome(trade['net']) if trade else 'neutral'),
                           'net': exact_text(trade['net']) if trade else None})
    return {'candles': [{**c, 'time': unix_time(c['open_time'])} for c in value.get('candles', [])],
            'executions': executions,
            'trades': [{'buy_time': unix_time(t['buy']['at']), 'sell_time': unix_time(t['sell']['at']),
                        'buy_price': t['buy']['price'], 'sell_price': t['sell']['price'],
                        'classification': outcome(t['net']), 'net': exact_text(t['net'])} for t in trades]}


def script_json(value):
    # Impede terminar o elemento script por IDs ou textos externos, inclusive </script>.
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).replace(
        '<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def candle_chart(value):
    if not value.get('candles'):
        return '<section class="panel" id="grafico"><h2>Candles e execuções</h2><p>Nenhum candle fechado disponível para o gráfico.</p></section>'
    trades = closed_trades(value)
    library = (ASSETS / LIBRARY).read_text(encoding='utf-8')
    controller = (ASSETS / 'chart.js').read_text(encoding='utf-8')
    if '</script' in library.lower() or '</script' in controller.lower():
        raise ValueError('Asset JavaScript contém fechamento HTML inesperado')
    parts = ['<section class="panel" id="grafico"><h2>Candles e execuções</h2>',
             '<p>COMPRA e VENDA marcadas no horário e preço efetivo do preenchimento. Horários em UTC.</p>',
             '<div class="chart-controls" id="chart-controls" hidden aria-label="Navegação do gráfico">'
             '<button type="button" data-chart-action="in" aria-label="Aproximar gráfico">Zoom +</button>'
             '<button type="button" data-chart-action="out" aria-label="Afastar gráfico">Zoom −</button>'
             '<button type="button" data-chart-action="all">Ver tudo</button>'
             '<button type="button" data-chart-action="recent">Últimos 60</button></div>',
             '<p class="chart-axis-title">Preço (USDT/BTC) · Escala fixa à esquerda</p>',
             '<div id="candle-chart" class="candle-chart" role="img" aria-label="Candles BTC/USDT com compras, vendas e resultados líquidos" '
             'aria-describedby="chart-help"></div>',
             '<p id="chart-error" role="alert" hidden></p>',
             '<noscript><p>Ative JavaScript para visualizar o gráfico. Ordens, execuções e resultados permanecem disponíveis nas tabelas.</p></noscript>',
             '<p id="chart-readout" class="chart-readout" aria-live="polite"></p>',
             '<img id="chart-print-image" class="chart-print-image" alt="Candles e execuções no instante da impressão">',
             '<p id="chart-help" class="muted">Arraste para navegar, use a roda do mouse ou os botões para zoom. '
             'O cursor exibe preço e horário; os detalhes abaixo preservam os valores exatos do replay.</p>',
             '<p class="chart-attribution">Gráfico por TradingView Lightweight Charts™ 5.2.0 · '
             '<a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView</a></p>',
             '<details class="chart-licenses"><summary>Licenças e atribuição do gráfico</summary>']
    for name in ('lightweight-charts-NOTICE.txt', 'lightweight-charts-LICENSE.txt', 'fancy-canvas-LICENSE.txt'):
        parts.append(f'<pre>{escape((ASSETS / name).read_text(encoding="utf-8"))}</pre>')
    parts.append('</details>')
    parts.append(f'<script id="chart-data" type="application/json">{script_json(chart_data(value))}</script>')
    parts.append(f'<script id="lightweight-charts-library">{library}</script>')
    parts.append(f'<script id="replayquant-chart-controller">{controller}</script>')
    parts.append('<div class="chart-legend"><span class="buy">▲ COMPRA</span><span class="neutral">▼ VENDA</span>'
                 '<span class="gain">Ganho líquido</span><span class="loss">Perda líquida</span>'
                 '<span class="neutral">Empate / posição aberta sem resultado</span></div>')
    if trades:
        parts.append('<div class="trade-results">')
        for t in trades:
            cls = outcome(t['net'])
            label = {'gain': 'Ganho líquido', 'loss': 'Perda líquida', 'neutral': 'Empate líquido'}[cls]
            parts.append(f'<p class="trade-result {cls}"><strong>{label}: {escape(exact_text(t["net"]))} USDT</strong>'
                         f' · Taxas das duas pontas: {escape(exact_text(t["fees"]))} USDT'
                         f' · Compra {escape(t["buy"]["at"])} → Venda {escape(t["sell"]["at"])}</p>')
        total = sum((t['net'] for t in trades), Fraction())
        parts.append(f'<p class="trade-total {outcome(total)}"><strong>Resultado líquido total das operações encerradas: '
                     f'{escape(exact_text(total))} USDT</strong></p>')
        parts.append('</div>')
    else:
        parts.append('<p class="muted">Nenhuma ida e volta encerrada; posição aberta não tem ganho ou perda realizada.</p>')
    parts.append('<p class="muted">Resultado líquido = recebimento da venda após taxa − desembolso da compra com taxa. '
                 'Slippage já incorporado aos preços. A cor do candle descreve seu preço, não o resultado da operação. '
                 'O gráfico mostra somente candles fechados processados; mova o cursor para consultar valores exatos.</p></section>')
    return ''.join(parts)
