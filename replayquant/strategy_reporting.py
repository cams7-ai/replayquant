"""Apresentação das avaliações modulares, a partir do replay comprometido."""
from html import escape
from .html_chart import ASSETS, script_json, unix_time
from .reporting import canonical, ratio_text, wire


def evaluation_rows(value):
    for evaluation in value['evaluations']:
        def formatted(values):
            return ', '.join(f'{key}={ratio_text(item)}' for key, item in (values or {}).items()) or '—'
        yield (evaluation['at'], evaluation['count'], evaluation['indicator_ready'],
               evaluation['signal_ready'], formatted(evaluation['previous_values']),
               formatted(evaluation['values']), evaluation['side'] or '—', evaluation['reason'],
               evaluation.get('diagnostic') or '—')


HEADERS = ('UTC', 'Contagem', 'Indicador pronto', 'Sinal pronto', 'Anterior exato',
           'Atual exato', 'Lado', 'Motivo', 'Diagnóstico')


def strategy_markdown(summary):
    from .exports import md_table
    value = wire(summary)
    strategy = value['strategy']
    return '\n'.join([
        '## Estratégia e avaliações', '',
        f"{strategy['name']} / versão {strategy['version']}", '',
        canonical(strategy['parameters']).decode(), '',
        canonical(value['indicator_policy']).decode(), '',
        md_table(HEADERS, evaluation_rows(value)), '',
    ]) + '\n'


def strategy_html(value):
    from .html_report import table
    strategy = value['strategy']
    rsi = strategy['name'] == 'RSI_REVERSION'
    unit = 'Pontos RSI (0–100)' if rsi else 'USDT/BTC'
    keys = ('rsi',) if rsi else ('short', 'long')
    series = []
    for key in keys:
        points = [{'time': unix_time(e['available_at']), 'value': e['values'][key]['value']}
                  for e in value['evaluations'] if e['values'][key] is not None]
        label = 'RSI' if rsi else ('SMA' if strategy['name'] == 'SMA_CROSS' else 'EMA') + (' curta' if key == 'short' else ' longa')
        series.append(dict(name=label, points=points))
    data = dict(rsi=rsi, series=series, parameters=strategy['parameters'])
    return ''.join([
        '<section class="panel strategy-panel" id="estrategia"><h2>Estratégia e causalidade</h2>',
        f"<p>{escape(strategy['name'])} / versão {strategy['version']} · {unit}</p>",
        '<p>Parâmetros '+escape(canonical(strategy['parameters']).decode())+'</p>',
        '<details><summary>Política numérica e inicialização</summary><p>'+escape(canonical(value['indicator_policy']).decode())+'</p></details>',
        '<p>Os pontos representam a disponibilidade no fechamento em UTC. Valores decimais exibidos com 12 casas e HALF_EVEN. Sinais usam razões exatas.</p>',
        '<div id="indicator-chart" class="candle-chart" role="img" aria-label="Indicadores da estratégia"></div>',
        '<p id="indicator-error" role="alert" hidden></p>',
        '<p id="indicator-readout" class="chart-readout"></p>',
        '<img id="indicator-print-image" class="chart-print-image" alt="Indicadores da estratégia na impressão">',
        '<noscript><p>Os indicadores e motivos permanecem disponíveis na tabela de avaliações.</p></noscript>',
        table(HEADERS, evaluation_rows(value), 'Razões exatas, aquecimento e motivos por fechamento'),
        table(('Sinal', 'Avaliação', 'UTC', 'Lado'),
              ((e['signal_id'], e['evaluation_id'], e['at'], e['side']) for e in value['signals']),
              'Sinais anteriores à decisão financeira'),
        table(('Decisão', 'Sinal', 'Ordem', 'Aprovada', 'Motivo'),
              ((e['decision_id'], e['signal_id'], e['order_id'], e['approved'], e['reason'] or '—')
               for e in value['decisions']), 'Decisões com risco e reservas'),
        f'<script id="indicator-data" type="application/json">{script_json(data)}</script>',
        '<script id="indicator-controller">'+(ASSETS/'indicators.js').read_text(encoding='utf-8')+'</script>',
        '</section>',
    ])
