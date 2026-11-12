"""Payload schema 4 e apresentação de risco a partir do estado já comprometido."""
from dataclasses import asdict
from html import escape
from .analysis import analyze
from .risk import POLICY

LIMITATIONS = [
    'Dados fictícios; risco planejado não é limite garantido de perda.',
    'Liquidez ilimitada assumida; slippage fixo adverso já no preço, sem modelo de spread.',
    'Stop/alvo somente a partir do candle seguinte à entrada: existe janela sem atuação da proteção.',
    'OHLC não revela caminho intraperíodo: STOP_FIRST é convenção, não sequência real.',
    'BAR_CLOSE_RESOLUTION: horário modelado no fechamento, intrabar desconhecido; duração/exposição aproximadas.',
    'Reservas não são custos; disponível + reservado = total; posição final KEEP_OPEN.',
    'Benchmarks passivos não seguem orçamento de risco, bloqueios ou stops da estratégia.',
    'Sem negociação real, anualização, aportes ou evidência de rentabilidade; USDT não é o próprio dólar.',
]


def enrich(summary, session):
    a = analyze(session)
    fills = {e['execution_id']: e for e in session.events if e['type'] == 'FILLED'}
    for trade in a['closed_trades']:
        event = fills[trade['sell_execution_id']]
        for key in ('exit_origin','execution_time_model','intrabar_time_known','interval_start','interval_end','ambiguous'):
            trade[key] = event[key]
    guard = session.guard.current or {}
    risk = dict(policy_version=POLICY, records=session.risk_records, parameters=asdict(session.config.risk),
                instrument_filters=session.config.instrument_filters,
                evaluations=[r for r in session.risk_records if r['record_type'] in ('EVALUATION','REVALIDATION')],
                reservations=session.ledger.history, protection_groups=session.protection_groups,
                equity_observations=session.guard.history,
                blocks={k: guard.get(k) for k in ('daily_blocked','drawdown_blocked','daily_base','daily_base_at')},
                execution_conventions=LIMITATIONS, reconciliation=session.ledger.reconcile())
    interrupted = session.status == 'INTERRUPTED'
    refused = any(o.status in ('REJECTED','UNEXECUTED') for o in session.orders)
    summary.update(schema_version=session.config.schema_version, input_config_schema_version=session.config.schema_version, simulation_mode=session.config.mode,
                   status=session.status, diagnostic=session.diagnostic,
                   exit_code=1 if interrupted else (2 if refused else 0), pending_order_id=session.pending,
                   candles=[e['candle'] for e in session.events if e['type'] == 'CLOSE'],
                   evaluations=[e for e in session.events if e['type'] == 'EVALUATION'],
                   signals=[e for e in session.events if e['type'] == 'SIGNAL'],
                   decisions=[e for e in session.events if e['type'] == 'DECISION'],
                   intentions=[e for e in session.events if e['type'] == 'INTENTION'],
                   risk=risk, analysis=a, limitations=LIMITATIONS)
    if session.config.mode == 'STRATEGY':
        a['ledger_entries'] = [{**asdict(e), 'schema_version': 5} for e in a['ledger_entries']]
        for benchmark in a['benchmarks']:
            benchmark['ledger_entries'] = [{**asdict(e), 'schema_version': 5} for e in benchmark['ledger_entries']]
        risk['reservations'] = [{**row, 'schema_version': 5} for row in risk['reservations']]
        summary.update(strategy=session.config.strategy, indicator_policy=session.config.strategy.policy)
    if interrupted:
        summary.update(round_trip_result=None, round_trip_reason='REPLAY_INTERRUPTED')
    for calc, fill in zip(summary['calculations'], session.fills):
        event = fills[fill.id]
        calc.update(reference_price=event['reference_price'], effective_price=fill.price,
                    fee_rate=session.config.fee_rate, slippage_rate=session.config.slippage_rate,
                    execution_time_model=event['execution_time_model'])
    return summary


def risk_markdown(summary):
    from .exports import md_table, cell
    from .reporting import wire, canonical
    risk = wire(summary['risk'])
    lines = ['## Risco, reservas e saídas protetivas', '',
             'R = P × r; L = E × (1+f) − S × (1−f).',
             'q = floor(min(R/L, (P×x−X)/E, B/(E×(1+f))) / step) × step.',
             'Taxas incluídas na perda planejada; slippage de saída é cenário adicional.', '',
             md_table(['Evento', 'Ordem', 'Aprovada / motivo', 'R USDT', 'E / S / T USDT/BTC', 'q candidata BTC', 'Desembolso USDT', 'Perda planejada USDT', 'Limitadores'],
                      _evaluation_rows(risk['evaluations'])), '',
             '### Candidatos exatos e contagem de incrementos', '',
             md_table(['Ordem','L USDT/BTC','q_risco BTC','q_exposição BTC','q_saldo BTC','step BTC','Incrementos','Perda com slippage de saída USDT'], _candidate_rows(risk)), '',
             '### Titularidade e liberações de reservas', '',
             md_table(['UTC','Ledger','Reserva','De','Para','Moeda','Quantidade','Estado'],
                      ((r['at'],r['ledger_id'],r['reservation_id'],r['from_owner_id'] or '—',r['owner_id'],r['currency'],r['quantity'],r['status']) for r in risk['reservations'])), '',
             '### Bloqueios patrimoniais', '',
             md_table(['UTC','Evento/fase','Patrimônio USDT','Base diária USDT','Perda diária (fração)','Drawdown (fração)','Diário bloqueado','DD bloqueado'],
                      ((r['at'],f"{r['source_event_seq']}/{r['phase']}",r['equity'],r['daily_base'] or r['daily_loss']['reason'],r['daily_loss']['value'],r['drawdown']['value'],r['daily_blocked'],r['drawdown_blocked']) for r in risk['equity_observations'])), '',
             '### Grupos de proteção e perda efetiva', '',
             md_table(['Grupo','S / T','q BTC','Elegível UTC','Estado','Origem / resolução','Ambíguo','Orçamento USDT','Realizado USDT'],
                      ((g['id'],f"{g['stop']} / {g['target']}",g['quantity'],g['eligible_at'],g['status'],
                        f"{(g['exit_details'] or {}).get('exit_origin','—')} / {(g['exit_details'] or {}).get('execution_time_model','—')}",
                        (g['exit_details'] or {}).get('ambiguous',False),g['budget'],(g['exit_details'] or {}).get('realized_pnl','—')) for g in risk['protection_groups'])), '',
             '### Convenções e risco residual', '']
    lines.extend('- '+cell(line) for line in risk['execution_conventions'])
    lines.extend(['', 'Parâmetros: '+cell(canonical(risk['parameters']).decode()),
                  '', 'Reconciliação de reservas: '+cell(risk['reconciliation']['status'])+'.'])
    return '\n'.join(lines)+'\n'


def _evaluation_rows(records):
    for record in records:
        p = record['payload']
        sizing = p.get('sizing') or p.get('details') or {}
        yield (f"{record['source_event_seq']}/{record['record_type']}", p['order_id'],
               p.get('reason') or ('APROVADA' if p.get('approved', True) else 'REJEITADA'),
               sizing.get('budget','—'), f"{sizing.get('entry','—')} / {sizing.get('stop','—')} / {sizing.get('target','—')}",
               sizing.get('candidate_quantity',sizing.get('quantity','—')), sizing.get('outlay','—'),
               sizing.get('planned_loss','—'), ', '.join(sizing.get('limiters',[])))


def _candidate_rows(risk):
    for record in risk['evaluations']:
        p=record['payload']
        s=p.get('sizing')
        if not s:
            continue
        def candidate(name):
            item=s['candidates'][name]
            return f"{item['value']} ({item['numerator']}/{item['denominator']})"
        yield (p['order_id'], s['loss_per_unit'], candidate('risk'), candidate('exposure'),
               candidate('cash'), risk['instrument_filters']['step'], s['increments'], s['slippage_exit_loss'])


def risk_html(value):
    from .html_report import table
    risk = value['risk']
    parts = ['<section class="panel risk-panel" id="risco"><h2>Risco, reservas e saídas protetivas</h2>',
             '<p>R = P × r; L = E × (1+f) − S × (1−f); q = floor(min(q_risco, q_exposição, q_saldo)/step) × step.</p>',
             '<p>Aprovação não é execução. Perda planejada inclui duas taxas; slippage de saída é cenário adicional.</p>',
             table(('Evento','Ordem','Decisão','Orçamento USDT','E / S / T USDT/BTC','q BTC','Desembolso USDT','Perda planejada USDT','Limitadores'), _evaluation_rows(risk['evaluations']), 'Dimensionamento e revalidação; sem ajuste retroativo'),
             '<h3>Candidatos exatos e incrementos</h3>',
             table(('Ordem','L USDT/BTC','q_risco BTC','q_exposição BTC','q_saldo BTC','step BTC','Incrementos','Perda com slippage USDT'), _candidate_rows(risk), 'Razões exatas para decisão; apresentação com 12 casas'),
             '<h3>Reservas: titularidade e liberação</h3>',
             table(('UTC','Reserva','Origem','Titular','Moeda','Quantidade','Estado'),
                   ((r['at'],r['reservation_id'],r['from_owner_id'] or '—',r['owner_id'],r['currency'],r['quantity'],r['status']) for r in risk['reservations']), 'Transferências não são custos'),
             '<h3>Caixa e BTC disponíveis/reservados</h3>',
             table(('UTC','Fase','Caixa total','Caixa disponível','Caixa reservado','BTC total','BTC disponível','BTC reservado'),
                   ((p['at'],p['phase'],p['cash_total'],p['cash_available'],p['cash_reserved'],p['asset_quantity'],p['asset_available'],p['asset_reserved']) for p in value['analysis']['equity_curve']), 'Disponível + reservado = total'),
             '<h3>Bloqueios persistentes</h3>',
             table(('UTC','Fase','Patrimônio','Base diária','Diário bloqueado','Drawdown bloqueado'),
                   ((r['at'],r['phase'],r['equity'],r['daily_base'] or r['daily_loss']['reason'],r['daily_blocked'],r['drawdown_blocked']) for r in risk['equity_observations']), 'Virada UTC redefine apenas bloqueio diário'),
             '<h3>Proteções e perda realizada</h3>',
             table(('Grupo','S / T','q BTC','Elegível UTC','Estado','Resolução','Ambíguo','Orçamento','Realizado'),
                   ((g['id'],f"{g['stop']} / {g['target']}",g['quantity'],g['eligible_at'],g['status'],
                     (g['exit_details'] or {}).get('execution_time_model','—'),(g['exit_details'] or {}).get('ambiguous',False),
                     g['budget'],(g['exit_details'] or {}).get('realized_pnl','—')) for g in risk['protection_groups']), 'STOP_FIRST quando ambos os níveis são tocados; intrabar desconhecido'),
             '<h3>Convenções e risco residual</h3><ul>']
    parts.extend('<li>'+escape(line)+'</li>' for line in risk['execution_conventions'])
    parts.append('</ul></section>')
    return ''.join(parts)
