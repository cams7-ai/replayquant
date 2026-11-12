"""Análise HTML e curvas por índice; conserva cada ponto de mesmo timestamp."""
from html import escape
from .exports import LABELS, FORMULAS, metric_text, analysis_formulas
from .html_chart import ASSETS, LIBRARY, script_json
from .reporting import canonical


def analysis_html(value, library_loaded=False):
    from .html_report import table
    a = value['analysis']
    parts = ['<section class="panel" id="analise"><h2>Patrimônio, métricas e referências</h2>',
             f"<p>Estado {escape(value['status'])} · Escopo {a['scope']} · Política {a['position_at_end']}</p>",
             f"<p>Horizonte UTC: {a['observation_start']} → {a['observed_until']}</p>",
             table(('Métrica', 'Valor', 'Razão exata'),
                   ((LABELS[k], metric_text(m), f"{m['numerator']}/{m['denominator']}" if m['numerator'] is not None else '—')
                    for k, m in sorted(a['metrics'].items())), 'Métricas calculadas no Python; sem anualização'),
             '<h3>Referências comparáveis</h3><p>Capital independente, mesmos custos e datas; exposições diferentes. Não somar carteiras.</p>',
             table(('Carteira', 'Estado', 'Patrimônio bruto USDT', 'Liquidação hipotética USDT', 'Retorno %', 'Taxas pagas USDT', 'Exposição %', 'Motivo'),
                   ((b['portfolio'], b['status'], b['metrics'].get('final_gross_equity', {}).get('value', '—'),
                     b['metrics'].get('final_hypothetical_liquidation_equity', {}).get('value', '—'),
                     b['metrics'].get('portfolio_return_pct', {}).get('value', '—'),
                     b['metrics'].get('paid_fees', {}).get('value', '—'),
                     b['metrics'].get('time_in_position_pct', {}).get('value', '—'), b['reason'] or '—') for b in a['benchmarks']),
                   'Patrimônios marcados e cenários hipotéticos separados'),
             '<h3>Curvas patrimoniais completas</h3><p>Eixo horizontal por índice de evento, com horário UTC nos detalhes. '
             'Pontos de mesmo timestamp permanecem distintos; o espaçamento visual não representa duração. '
             'Cada carteira tem sua própria sequência. O drawdown usa todos esses pontos.</p>',
             '<noscript><p>Ative JavaScript para as curvas; consulte abaixo os pontos exatos e métricas sem JavaScript.</p></noscript>']
    datasets = []
    for name, color, curve in [('STRATEGY', '#087e83', a['equity_curve'])] + [
            (b['portfolio'], '#64748b' if b['portfolio'] == 'HOLD_USDT' else '#9260b8', b['equity_curve']) for b in a['benchmarks']]:
        if not curve:
            continue
        label = {'STRATEGY': 'Estratégia', 'HOLD_USDT': 'Manter USDT', 'BUY_HOLD_BTC': 'Comprar e manter BTC'}[name]
        parts.extend([f'<article class="equity-panel"><h3>{label} ({name})</h3>',
                      '<p class="muted">Patrimônio bruto em USDT · Índice de evento; detalhes em UTC</p>',
                      f'<button class="equity-fit" id="equity-fit-{name}" type="button">Ver curva completa</button>',
                      f'<div class="equity-chart" id="equity-{name}" role="img" aria-label="Curva patrimonial {name}"></div>',
                      f'<p class="chart-readout equity-readout" id="equity-readout-{name}" aria-live="polite"></p>',
                      f'<p id="equity-error-{name}" hidden role="alert"></p>',
                      f'<img class="equity-print" id="equity-print-{name}" alt="Curva patrimonial {name}"></article>'])
        datasets.append(dict(portfolio=name, color=color, points=curve))
    if not library_loaded:
        parts.append('<p class="chart-attribution">TradingView Lightweight Charts™ 5.2.0 · '
                     '<a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView</a></p>'
                     '<details class="chart-licenses"><summary>Licenças e atribuição</summary>')
        for name in ('lightweight-charts-NOTICE.txt', 'lightweight-charts-LICENSE.txt', 'fancy-canvas-LICENSE.txt'):
            parts.append(f'<pre>{escape((ASSETS/name).read_text(encoding="utf-8"))}</pre>')
        parts.append('</details>')
        parts.append(f'<script id="lightweight-charts-library">{(ASSETS/LIBRARY).read_text(encoding="utf-8")}</script>')
    parts.extend([f'<script id="equity-data" type="application/json">{script_json(datasets)}</script>',
                  f'<script id="equity-controller">{(ASSETS/"equity.js").read_text(encoding="utf-8")}</script>',
                  '<h3>Reconciliação e memória de cálculo</h3>',
                  f"<p>Taxa: {a['execution_cost_policy']['fee_rate']} · Slippage: {a['execution_cost_policy']['slippage_rate']} · Quantidade: {a['execution_cost_policy']['strategy_quantity'] if value['schema_version'] not in (4, 5) else 'variável por risco'} BTC</p>",
                  f"<p>Reconciliação: {a['reconciliation']['status']} · Capital inicial {value['initial_cash']} USDT · "
                  f"Caixa reconstruído {a['reconciliation']['reconstructed_cash']} USDT · BTC {a['reconciliation']['reconstructed_asset']}</p>",
                  '<details><summary>Todos os pontos exatos da estratégia</summary>',
                  table(('Ponto', 'UTC', 'Fase', 'Caixa USDT', 'BTC', 'Marca USDT/BTC', 'Base USDT', 'Realizado USDT', 'Não realizado USDT', 'Patrimônio USDT', 'Liquidação hipotética USDT'),
                        ((p['point_seq'], p['at'], p['phase'], p['cash_total'], p['asset_quantity'],
                          p['mark_price'] if p['mark_price'] is not None else p['mark_reason'], p['cost_basis'],
                          p['realized_pnl'], p['unrealized_pnl'], p['gross_equity'], p['hypothetical_liquidation_equity']) for p in a['equity_curve']),
                        'Aberturas, preenchimentos e fechamentos; sem sobrescrever eventos de mesmo horário'), '</details>',
                  '<h3>Operações encerradas</h3>',
                  table(('Trade', 'Compra UTC', 'Venda UTC', 'Desembolso USDT', 'Recebimento USDT', 'Taxas BUY/SELL USDT', 'Líquido USDT', 'Retorno', 'Duração s'),
                        ((t['trade_id'], t['buy_at'], t['sell_at'], t['cash_outflow'], t['cash_inflow'],
                          f"{t['buy_fee']} / {t['sell_fee']}", t['net_pnl'], metric_text(t['return_pct']), t['duration_seconds']) for t in a['closed_trades']),
                        'Somente pares encerrados; taxas inclusas'), '<h3>Drawdown e duração</h3>',
                  table(('Pico UTC / ponto', 'Vale UTC / ponto', 'Queda USDT', 'Drawdown %', 'Recuperação', 'Duração s', 'Motivo'),
                        ((f"{e['peak_at']} / {e['peak_point_seq']}", f"{e['trough_at']} / {e['trough_point_seq']}",
                          e['drawdown_amount'], e['drawdown_pct']['value'], e['recovery_at'] or '—', e['duration_seconds'], e['reason'] or 'RECOVERED') for e in a['drawdown_episodes']),
                        a['episode_reason'] or 'Duração em segundos; episódio sem recuperação é parcial'),
                  '<h3>Posição aberta</h3>'])
    if a['open_position']:
        pos = a['open_position']
        parts.append(f"<p>{pos['quantity']} BTC · Base {pos['cost_basis']} USDT · Não realizado {pos['unrealized_pnl']} USDT · "
                     f"Taxa hipotética de saída {pos['hypothetical_exit_fee']} USDT · Slippage hipotético {pos['hypothetical_exit_slippage']} USDT (não pagos).</p>")
    else:
        parts.append('<p>Posição zerada, sem liquidação adicional.</p>')
    parts.append('<h3>Memória de entrada dos benchmarks</h3>')
    for b in a['benchmarks']:
        parts.append(f"<p>{b['portfolio']}: {escape(canonical(b['parameters']).decode('utf-8'))}</p>")
    parts.append('<h3>Fórmulas e limites</h3><ul>')
    parts.extend(f'<li>{escape(line)}</li>' for line in analysis_formulas(value))
    parts.append('</ul></section>')
    return ''.join(parts)
