"""Gráfico SVG offline; razões exatas nos valores, float somente em pixels."""
from datetime import datetime
from fractions import Fraction
from html import escape


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


def candle_chart(value):
    candles = value.get('candles', [])
    if not candles:
        return '<section class="panel" id="grafico"><h2>Candles e execuções</h2><p>Nenhum candle fechado disponível para o gráfico.</p></section>'
    trades = closed_trades(value)
    results = {t['sell']['id']: t for t in trades}
    prices = [Fraction(c[k]) for c in candles for k in ('low', 'high')]
    prices.extend(Fraction(f['price']) for f in value['fills'])
    low, high = min(prices), max(prices)
    pad = (high - low) / 8 if high > low else high / 100
    low, high = low - pad, high + pad
    width = max(960, len(candles) * 64 + 150)
    left, right, top, bottom = 108, width - 38, 58, 360
    step = (right - left) / len(candles)

    def y(price):
        return top + float((high - Fraction(price)) / (high - low)) * (bottom - top)

    def x(index):
        return left + (index + .5) * step

    positions = {datetime.fromisoformat(c['open_time']): i for i, c in enumerate(candles)}
    parts = ['<section class="panel" id="grafico"><h2>Candles e execuções</h2>',
             '<p>COMPRA e VENDA marcadas no horário e preço efetivo do preenchimento. Horários em UTC.</p>',
             '<div class="chart-scroll"><svg class="candle-chart" xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {width} 470" style="min-width:{width}px" role="img" aria-labelledby="chart-title chart-desc">',
             '<title id="chart-title">Candles BTC/USDT com compras, vendas e resultado líquido</title>',
             '<desc id="chart-desc">Candles verdes indicam alta e vermelhos queda. Compra azul; venda e ligação verdes em ganho, '
             'vermelhas em perda e cinzas em empate, após taxas. Apenas execuções realizadas são marcadas.</desc>',
             f'<rect width="{width}" height="470" fill="white"></rect>']
    for i in range(5):
        price = high - (high - low) * Fraction(i, 4)
        yy = y(price)
        parts.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="#e2e8f0"></line>'
                     f'<text x="{left-12}" y="{yy+4:.2f}" text-anchor="end" class="axis-label">{escape(exact_text(price))}</text>')
    parts.append(f'<text x="{left}" y="26" class="axis-label">Preço (USDT/BTC)</text>')
    for t in trades:
        bi = positions.get(datetime.fromisoformat(t['buy']['at']))
        si = positions.get(datetime.fromisoformat(t['sell']['at']))
        if bi is None or si is None:
            continue
        cls = outcome(t['net'])
        parts.append(f'<path class="trade-link {cls}" d="M {x(bi):.2f} {y(t["buy"]["price"]):.2f} '
                     f'L {x(si):.2f} {y(t["sell"]["price"]):.2f}">'
                     f'<title>Resultado líquido: {escape(exact_text(t["net"]))} USDT; taxas: {escape(exact_text(t["fees"]))} USDT</title></path>')
    for i, c in enumerate(candles):
        xx = x(i)
        rising = Fraction(c['close']) >= Fraction(c['open'])
        color = '#16835b' if rising else '#c23b45'
        yo, yc = y(c['open']), y(c['close'])
        body = max(1.5, abs(yo - yc))
        body_width = min(26, step * .45)
        title = (f"{c['open_time']} UTC | Abertura {c['open']} · Máxima {c['high']} · "
                 f"Mínima {c['low']} · Fechamento {c['close']} USDT/BTC")
        parts.append(f'<g class="candle" data-open-time="{escape(c["open_time"], quote=True)}"><title>{escape(title)}</title>'
                     f'<line x1="{xx:.2f}" y1="{y(c["high"]):.2f}" x2="{xx:.2f}" y2="{y(c["low"]):.2f}" stroke="{color}" stroke-width="2"></line>'
                     f'<rect x="{xx-body_width/2:.2f}" y="{min(yo,yc):.2f}" width="{body_width:.2f}" height="{body:.2f}" fill="{color}"></rect></g>')
        if i % max(1, len(candles) // 10) == 0 or i == len(candles) - 1:
            dt = datetime.fromisoformat(c['open_time'])
            parts.append(f'<text x="{xx:.2f}" y="397" text-anchor="middle" class="axis-label">{dt:%H:%M}</text>'
                         f'<text x="{xx:.2f}" y="414" text-anchor="middle" class="axis-date">{dt:%d/%m/%Y}</text>')
    for f in value['fills']:
        i = positions.get(datetime.fromisoformat(f['at']))
        if i is None:
            continue
        xx, yy = x(i), y(f['price'])
        buy = f['side'] == 'BUY'
        trade = results.get(f['id'])
        cls = 'buy' if buy else (outcome(trade['net']) if trade else 'neutral')
        label = 'COMPRA' if buy else 'VENDA'
        direction = 1 if buy else -1
        # A ponta do triângulo coincide com o preço efetivo, não com o sinal.
        points = f'{xx:.2f},{yy:.2f} {xx-7:.2f},{yy+direction*13:.2f} {xx+7:.2f},{yy+direction*13:.2f}'
        title = (f"{label} {f['at']} | {f['quantity']} BTC a {f['price']} USDT/BTC | taxa {f['fee']} USDT")
        if trade:
            title += f" | Resultado líquido {exact_text(trade['net'])} USDT (taxas incluídas)"
        parts.append(f'<g class="execution-marker {cls}" data-execution-id="{escape(f["id"], quote=True)}">'
                     f'<title>{escape(title)}</title><polygon points="{points}"></polygon>'
                     f'<text x="{xx:.2f}" y="{yy+direction*31:.2f}" text-anchor="middle" class="marker-label">{label}</text></g>')
    parts.append(f'<text x="{right}" y="452" text-anchor="end" class="axis-label">Abertura do candle · UTC</text></svg></div>'
                 '<div class="chart-legend"><span class="buy">▲ COMPRA</span><span class="neutral">▼ VENDA</span><span class="gain">Ganho líquido</span>'
                 '<span class="loss">Perda líquida</span><span class="neutral">Empate / posição aberta sem resultado</span></div>')
    if trades:
        parts.append('<div class="trade-results">')
        for t in trades:
            cls = outcome(t['net'])
            label = {'gain': 'Ganho líquido', 'loss': 'Perda líquida', 'neutral': 'Empate líquido'}[cls]
            parts.append(f'<p class="trade-result {cls}"><strong>{label}: {escape(exact_text(t["net"]))} USDT</strong>'
                         f' · Taxas das duas pontas: {escape(exact_text(t["fees"]))} USDT'
                         f' · Compra {escape(t["buy"]["at"])} → Venda {escape(t["sell"]["at"])}</p>')
        parts.append('</div>')
    else:
        parts.append('<p class="muted">Nenhuma ida e volta encerrada; posição aberta não tem ganho ou perda realizada.</p>')
    parts.append('<p class="muted">Resultado líquido = recebimento da venda após taxa − desembolso da compra com taxa. '
                 'Slippage já incorporado aos preços. A cor do candle descreve seu preço, não o resultado da operação. '
                 'O gráfico mostra somente candles fechados processados; passe o ponteiro para consultar valores.</p></section>')
    return ''.join(parts)
