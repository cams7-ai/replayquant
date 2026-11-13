"""Projeções schema 7: quinze artefatos, referências isoladas e HTML offline."""
from dataclasses import asdict
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from html import escape
from pathlib import Path
import platform

from .execution import effective_price
from .exports import csv_text, md_table
from .metrics import percentage, ratio, metric
from .reporting import canonical, json_text, wire
from .shared_engine import POLICIES
from .validation import financial
from .shared_engine import MINUTE

ZERO = Decimal('0')


def shared_manifest(inputs):
    root = Path(__file__).resolve().parent.parent
    paths = sorted([p for p in (root/'replayquant').rglob('*') if p.is_file()
                    and (p.suffix == '.py' or 'assets' in p.parts)]
                   + [root/k for k in ('pyproject.toml', 'requirements.lock', '.python-version')])
    files = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths}
    identity = dict(config=inputs.config, datasets=dict(inputs.data_hashes), policies=POLICIES,
                    code_hash=sha256(canonical(files)).hexdigest(), python_version=platform.python_version())
    return dict(schema_version=7, run_id=sha256(canonical(identity)).hexdigest(), **identity,
                recipe_hash=inputs.recipe_hash, code_files=files, dependencies=[], seed=None,
                seed_reason='NO_RANDOMNESS', decimal_policy=dict(precision=40, inexact='ERROR'),
                execution_model='NEXT_OPEN_FULL_UNLIMITED_LIQUIDITY')


@financial
def benchmarks(session, inputs):
    c = session.config
    accepted = [e for e in session.events if e['type'] == 'MARK_BATCH' and e['phase'] == 'OPEN_MARKS']
    first = {}
    for event in accepted:
        for symbol, mark in event['marks'].items():
            first.setdefault(symbol, (mark, event['at']))
    cash, positions, fees, entries = c.initial_cash, {}, ZERO, []
    n = len(c.instrument_limits)
    for symbol, _ in c.instrument_limits:
        if symbol not in first:
            entries.append(dict(symbol=symbol, quantity=ZERO, reason='NO_ELIGIBLE_OPEN', at=None))
            continue
        reference, at = first[symbol]
        entry = effective_price(reference, 'BUY', c.slippage_rate)
        f = c.instrument(symbol).instrument_filters
        raw = Fraction(c.initial_cash)/n/Fraction(entry*(1+c.fee_rate))
        q = Decimal(raw//Fraction(f.step))*f.step
        if q < f.min_quantity or q*entry < f.min_notional:
            entries.append(dict(symbol=symbol, quantity=ZERO, reason='BELOW_MINIMUMS', at=at))
            continue
        cost = q*entry*(1+c.fee_rate)
        cash -= cost
        fees += q*entry*c.fee_rate
        positions[symbol] = q
        entries.append(dict(symbol=symbol, quantity=q, entry_price=entry, fee=q*entry*c.fee_rate,
                            cash_outflow=cost, at=at, reason=None))
    gross = cash+sum((q*session.marks[s][0] for s, q in positions.items()), ZERO)
    liquidation = cash+sum((q*session.marks[s][0]*(1-c.slippage_rate)*(1-c.fee_rate)
                            for s, q in positions.items()), ZERO)
    reason = 'PORTFOLIO_UNAVAILABLE' if session.unavailable or not accepted else None
    return [dict(portfolio='HOLD_USDT', initial_cash=c.initial_cash, cash=c.initial_cash, paid_fees=ZERO,
                 gross_equity=None if reason else c.initial_cash, hypothetical_liquidation_equity=None if reason else c.initial_cash,
                 return_pct=metric(None, '%', reason) if reason else percentage(ZERO, c.initial_cash), reason=reason,
                 observation_start=c.window.start, observed_until=session.at),
            dict(portfolio='BUY_HOLD_BASKET', initial_cash=c.initial_cash, cash=cash, positions=positions, paid_fees=fees,
                 gross_equity=None if reason else gross, hypothetical_liquidation_equity=None if reason else liquidation,
                 return_pct=metric(None, '%', reason) if reason else percentage(gross-c.initial_cash, c.initial_cash),
                 entries=entries, reason=reason, allocation_per_asset=ratio(Fraction(1, n), 'FRACTION'),
                 observation_start=c.window.start, observed_until=session.at)]


@financial
def shared_report(session, inputs, metadata):
    total, parts = session.equities()
    realized = sum((t['net_pnl'] for t in session.trades), ZERO)
    reserves = [r for r in session.reserves.values() if r['status'] == 'ACTIVE']
    assets = {}
    for asset, quantity in sorted(session.assets.items()):
        reserved = sum((r['amount'] for r in reserves if r['asset'] == asset), ZERO)
        symbol = next(s for s, _ in session.config.instrument_limits if session.config.instrument(s).base_asset == asset)
        mark = session.marks.get(symbol)
        assets[asset] = dict(total=quantity, available=quantity-reserved, reserved=reserved,
                             mark_price=mark[0] if mark else None, mark_at=mark[1] if mark else None,
                             mark_age_seconds=int((session.at-mark[1]).total_seconds()) if mark else None,
                             mark_reason=None if mark else 'PRICE_MISSING')
        assets[asset].update(gross_value=quantity*mark[0] if mark else (ZERO if not quantity else None),
                             hypothetical_liquidation_value=quantity*mark[0]*(1-session.config.slippage_rate)*(1-session.config.fee_rate) if mark else (ZERO if not quantity else None),
                             realized_pnl=sum((t['net_pnl'] for t in session.trades if t['symbol'] == symbol), ZERO))
    allocations = []
    for owner in sorted(session.accounts):
        pnl = parts[owner]-session.initial[owner]
        allocations.append(dict(strategy_id=owner, initial_allocation=session.initial[owner],
                                cash_total=session.accounts[owner], cash_available=session.accounts[owner]-session.reserved_cash(owner),
                                cash_reserved=session.reserved_cash(owner), equity=parts[owner], pnl=pnl,
                                contribution_pct=percentage(pnl, session.config.initial_cash),
                                own_return_pct=percentage(pnl, session.initial[owner]) if session.initial[owner] else None))
    joint = held = 0
    joint_periods = []
    peak = session.config.initial_cash
    max_dd = Fraction()
    max_dd_amount = ZERO
    dd_start = None
    dd_duration = 0
    for i, point in enumerate(session.equity):
        value = point['gross_equity']
        if value >= peak:
            peak = value
            dd_start = None
        else:
            if dd_start is None:
                dd_start = session.equity[max(0, i-1)]['at']
            dd_duration = max(dd_duration, int((point['at']-dd_start).total_seconds()))
        max_dd_amount = max(max_dd_amount, peak-value)
        max_dd = max(max_dd, Fraction(peak-value)/Fraction(peak))
        if i+1 < len(session.equity):
            dt = int((session.equity[i+1]['at']-point['at']).total_seconds())
            count = sum(q > 0 for q in point['assets'].values())
            held += dt if count else 0
            joint += dt if count > 1 else 0
            if count > 1 and dt:
                bases = sorted(a for a, q in point['assets'].items() if q > 0)
                end = session.equity[i+1]['at']
                if joint_periods and joint_periods[-1]['end'] == point['at'] and joint_periods[-1]['assets'] == bases:
                    joint_periods[-1]['end'] = end
                    joint_periods[-1]['duration_seconds'] += dt
                else:
                    joint_periods.append(dict(start=point['at'], end=end, assets=bases, duration_seconds=dt))
    reason = 'PORTFOLIO_UNAVAILABLE' if session.unavailable else None
    metrics = dict(initial_cash=session.config.initial_cash, final_cash=session.cash, final_gross_equity=total,
                   realized_pnl=realized, unrealized_pnl=total-session.config.initial_cash-realized,
                   paid_fees=session.fees, slippage_impact=session.slippage,
                   hypothetical_liquidation_equity=session.equity[-1]['hypothetical_liquidation_equity'],
                   portfolio_return_pct=metric(None, '%', reason) if reason else percentage(total-session.config.initial_cash, session.config.initial_cash),
                   max_drawdown_pct=metric(None, '%', reason) if reason else ratio(max_dd*100, '%'),
                   max_drawdown_amount=None if reason else max_dd_amount,
                   max_drawdown_duration_seconds=None if reason else dd_duration,
                   time_in_position_seconds=None if reason else held,
                   joint_exposure_seconds=None if reason else joint,
                   observation_duration_seconds=None if reason else int((session.at-session.config.window.start).total_seconds()),
                   closed_trade_count=len(session.trades))
    x, k = session.commitments()
    exposure_limits = []
    def excess(scope, identity, committed, cap):
        exposure_limits.append(dict(scope=scope, identity=identity, committed=committed, limit=cap,
                                    excess=max(ZERO, committed-cap)))
    excess('PORTFOLIO', 'PORTFOLIO', x, total*session.config.portfolio.exposure_fraction)
    excess('OPEN_RISK', 'PORTFOLIO', k, total*session.config.portfolio.max_open_risk_fraction)
    for symbol, limit in session.config.instrument_limits:
        excess('INSTRUMENT', symbol, session.commitments(symbol=symbol)[0], total*limit)
    for owner, spec in session.owners.items():
        excess('STRATEGY', owner, session.commitments(owner=owner)[0], parts[owner]*spec.risk.exposure_fraction)
    coverage = []
    for row in inputs.coverage:
        symbol = row['symbol']
        instrument = session.config.instrument(symbol)
        expected_times = []
        at = session.config.window.start
        while at < session.config.window.end:
            if instrument.contains(at, at+MINUTE):
                expected_times.append(at)
            at += MINUTE
        eligible = dict(inputs.datasets)[symbol]
        accepted = [c for c in eligible if c.close_time <= session.at and any(
            e['type'] == 'MARK_BATCH' and e['phase'] == 'CLOSE_MARKS' and e['at'] == c.close_time
            and symbol in e['marks'] for e in session.events)]
        present = {c.open_time for c in eligible}
        missing = [t for t in expected_times if t not in present]
        coverage.append(dict(row, eligible_count=len(eligible), accepted=len(accepted), expected=len(expected_times),
                             first_eligible=eligible[0].open_time if eligible else None,
                             last_eligible=eligible[-1].close_time if eligible else None,
                             missing_openings=missing, observed_until=session.at,
                             coverage='NONE' if not accepted else ('FULL' if len(accepted)*60 == int((session.config.window.end-session.config.window.start).total_seconds()) else 'PARTIAL'),
                             reason='DATA_GAP' if missing and session.interrupted else row['reason']))
    lots = []
    for lot in session.lots.values():
        l = dict(lot)
        mark = session.marks.get(l['symbol'])
        if l['status'] == 'OPEN' and mark:
            l.update(mark_price=mark[0], mark_at=mark[1], gross_value=l['quantity']*mark[0],
                     unrealized_pnl=l['quantity']*mark[0]-l['cost_basis'],
                     hypothetical_liquidation_value=l['quantity']*mark[0]*(1-session.config.slippage_rate)*(1-session.config.fee_rate))
        lots.append(l)
    result = dict(schema_version=7, run_id=metadata['run_id'], mode='SHARED_PORTFOLIO',
                status='INTERRUPTED' if session.interrupted else ('PORTFOLIO_UNAVAILABLE' if session.unavailable else 'COMPLETED'),
                exit_code=session.exit_code, source=session.config.source, quote_asset='USDT', interval='1m',
                initial_cash=session.config.initial_cash, policies=POLICIES, config=session.config,
                balances=dict(cash_total=session.cash, cash_available=session.cash-session.reserved_cash(),
                              cash_reserved=session.reserved_cash(), assets=assets),
                metrics=metrics, allocations=allocations, lots=lots,
                joint_exposure_periods=joint_periods,
                contributions=session.contributions, exposure=session.exposure, limits=exposure_limits,
                events=session.events, ledger=session.ledger, reservations=session.reservations, risk=session.risk,
                equity=session.equity, fills=session.fills, trades=session.trades, orders=list(session.orders.values()),
                evaluations=session.evaluations, signals=session.signals, decisions=session.decisions,
                coverage=coverage, observed_until=session.at, observation_start=session.config.window.start,
                benchmarks=benchmarks(session, inputs), reconciliation=session.reconcile(),
                candles={s: [c for c in candles if c.close_time <= session.at]
                         for s, candles in inputs.datasets},
                limitations=['Dados fictícios e amostra curta; sem evidência de rentabilidade.',
                             'USDT é unidade de cotação; não se presume identidade com USD.',
                             'Liquidez ilimitada, fills integrais na próxima abertura, sem latência positiva.',
                             'STOP_FIRST e BAR_CLOSE_RESOLUTION são convenções; OHLC não revela trajetória intraperíodo.',
                             'BOUNDARY_MARKS_V1 condiciona drawdown, duração e exposição à sequência modelada.',
                             'Risco planejado não garante perda máxima: gaps e slippage podem superá-lo.',
                             'Posições simultâneas expõem conjuntamente; não se infere hedge ou correlação estatística.',
                             'KEEP_OPEN conserva posições; liquidação hipotética não cobra taxa nem gera fill.',
                             'Benchmarks usam capital independente e não obedecem aos bloqueios das estratégias.'])

    if session.config.provenance:
        from .provenance import enrich_historical
        enrich_historical(result, session.config.provenance)
    return result


def _tables(summary):
    s = wire(summary)
    sections = [
        ('Políticas', ['Política', 'Valor'], list(s['policies'].items())),
        ('Saldos físicos', ['Caixa total USDT', 'Disponível USDT', 'Reservado USDT'],
         [[s['balances'][k] for k in ('cash_total', 'cash_available', 'cash_reserved')]]),
        ('Ativos físicos', ['Moeda', 'Total base', 'Disponível base', 'Reservado base', 'Marca USDT/base', 'UTC', 'Idade s'],
         [[a, *[v[k] for k in ('total', 'available', 'reserved', 'mark_price', 'mark_at', 'mark_age_seconds')]] for a, v in s['balances']['assets'].items()]),
        ('Atribuições e contribuições', ['Titular', 'Inicial USDT', 'Caixa USDT', 'Patrimônio USDT', 'PnL USDT', 'Contribuição % global', 'Retorno próprio %'],
         [[a['strategy_id'], a['initial_allocation'], a['cash_total'], a['equity'], a['pnl'], a['contribution_pct']['value'],
           a['own_return_pct']['value'] if a['own_return_pct'] else '—'] for a in s['allocations']]),
        ('Métricas', ['Métrica', 'Valor'], [[k, v['value'] if isinstance(v, dict) and 'value' in v else v] for k, v in s['metrics'].items()]),
        ('Períodos de exposição conjunta', ['Início UTC', 'Fim UTC', 'Ativos', 'Duração s'],
         [[p[k] for k in ('start','end','assets','duration_seconds')] for p in s['joint_exposure_periods']]),
        ('Indicadores por binding', ['UTC', 'Titular', 'Par', 'Pronto', 'Sinal pronto', 'Motivo', 'Valores e razões exatas'],
         [[e['at'], e['strategy_id'], e['symbol'], e['evaluation']['indicator_ready'],
           e['evaluation']['signal_ready'], e['evaluation']['reason'], e['evaluation']['values']] for e in s['evaluations']]),
        ('Lotes e proteções', ['Lote', 'Titular', 'Instrumento', 'Quantidade base', 'Estado', 'Stop USDT/base', 'Alvo USDT/base', 'Risco USDT', 'Proteção'],
         [[l[k] for k in ('lot_id', 'strategy_id', 'symbol', 'quantity', 'status', 'stop', 'target', 'planned_loss', 'protection_status')] for l in s['lots']]),
        ('Execuções', ['Seq', 'UTC', 'Fase', 'Titular', 'Par', 'Lote', 'Lado', 'Quantidade base', 'Referência USDT/base', 'Efetivo USDT/base', 'Taxa USDT'],
         [[f[k] for k in ('seq', 'at', 'phase', 'strategy_id', 'symbol', 'lot_id', 'side', 'quantity', 'reference_price', 'effective_price', 'fee')] for f in s['fills']]),
        ('Arbitragem e motivos', ['Seq', 'Titular', 'Par', 'Lado', 'Aprovada', 'Motivo', 'Memória exata'],
         [[d['seq'], d['strategy_id'], d['symbol'], d['side'], d['approved'], d['reason'], d['sizing']] for d in s['decisions']]),
        ('Limites e excessos', ['Escopo', 'Identidade', 'Comprometido USDT', 'Teto USDT', 'Excesso USDT'],
         [[l[k] for k in ('scope', 'identity', 'committed', 'limit', 'excess')] for l in s['limits']]),
        ('Revalidações na abertura', ['Seq', 'Titular', 'Ordem', 'Preço USDT/base', 'Risco USDT', 'Desembolso USDT', 'Motivo'],
         [[r.get(k) for k in ('seq', 'strategy_id', 'order_id', 'entry', 'planned_loss', 'outlay', 'reason')]
          for r in s['risk'] if r.get('record_type') == 'REVALIDATION']),
        ('Bloqueios patrimoniais', ['UTC', 'Titular/escopo', 'Fase', 'Patrimônio USDT', 'Base diária USDT', 'Pico USDT', 'Diário bloqueado', 'Drawdown bloqueado'],
         [[r.get(k) for k in ('at', 'strategy_id', 'phase', 'equity', 'daily_base', 'peak', 'daily_blocked', 'drawdown_blocked')]
          for r in s['risk'] if r.get('record_type') == 'GUARD' and (r.get('daily_blocked') or r.get('drawdown_blocked'))]),
        ('Reservas comuns', ['Seq', 'Titular', 'Moeda', 'Quantidade', 'Ação', 'Detentor', 'Lote'],
         [[r[k] for k in ('seq', 'strategy_id', 'asset', 'amount', 'action', 'holder', 'lot_id')] for r in s['reservations']]),
        ('Cobertura', ['Instrumento', 'Aceitos', 'Excluídos', 'Duplicatas', 'Disponível desde UTC', 'Disponível até UTC', 'Motivo'],
         [[c[k] for k in ('symbol', 'accepted', 'excluded', 'duplicates', 'available_from', 'available_until', 'reason')] for c in s['coverage']]),
        ('Referências isoladas', ['Referência', 'Capital USDT', 'Caixa USDT', 'Patrimônio bruto USDT', 'Liquidação hipotética USDT', 'Taxas USDT', 'Retorno %', 'Motivo'],
         [[b['portfolio'], b['initial_cash'], b['cash'], b['gross_equity'], b['hypothetical_liquidation_equity'], b['paid_fees'], b['return_pct']['value'], b['reason']] for b in s['benchmarks']]),
        ('Reconciliação', ['Estado', 'Caixa reconstruído USDT', 'Ativos base'],
         [[s['reconciliation'][k] for k in ('status', 'reconstructed_cash', 'assets')]])]
    if s.get('provenance'):
        sections.insert(0, ('Origem e proveniência', ['Origem','Versão','Ingestão','Qualidade','Universo','Política'],
                          [[p['source'],p['dataset_version'],p['ingestion_id'],p['quality_status'],p['universe']['basis'],p['policy']] for p in s['provenance']]))
    return sections


def shared_markdown(summary):
    lines = ['# ReplayQuant — Sprint 12: carteira compartilhada', '',
             f"Execução: {summary['run_id']} · Estado: {summary['status']} · Código: {summary['exit_code']}", '',
             'Um capital global, atribuições auditáveis; contribuições usam o capital global inicial.', '']
    for title, headers, rows in _tables(summary):
        lines += ['## '+title, '', md_table(headers, rows), '']
    lines += ['## Fórmulas e limitações', '',
              'C = C_UNALLOCATED + Σ C_i; Q_base = Σ q_lote; P = C + Σ Q_base × marca = C_UNALLOCATED + Σ P_i.', '',
              'PnL_i = realizado_i + não realizado_i = P_i − A_i; contribuição_i = PnL_i / capital_global × 100.', '',
              'Reservas já integram os saldos totais e não são somadas novamente. Retornos próprios não são somados.', '',
              *['- '+line for line in summary['limitations']]]
    return '\n'.join(lines)+'\n'


def _chart(points, title, unit):
    """SVG usa float apenas na geometria; valores exatos ficam em title/tabelas."""
    if not points:
        return '<p>Sem observações elegíveis.</p>'
    values = [float(v) for _, v in points]
    lo, hi = min(values), max(values)
    spread = hi-lo or max(abs(hi)*.01, 1)
    def xy(i, v):
        return 65+(830*i/max(1,len(points)-1)), 215-170*(float(v)-lo)/spread
    path = ' '.join(f'{xy(i,v)[0]:.2f},{xy(i,v)[1]:.2f}' for i, (_, v) in enumerate(points))
    marks = []
    for i, (at, v) in enumerate(points):
        x, y = xy(i,v)
        marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2"><title>{escape(str(at))}: {escape(str(v))} {escape(unit)}</title></circle>')
    return (f'<figure><figcaption>{escape(title)} · {escape(unit)} · sequência de observações</figcaption><svg role="img" aria-label="{escape(title)}" viewBox="0 0 940 270">'
            f'<text x="5" y="25">{hi:.8g}</text><text x="5" y="235">{lo:.8g}</text>'
            f'<polyline fill="none" stroke="#147d92" stroke-width="2" points="{path}"/>'+''.join(marks)+
            f'<text x="65" y="260">{escape(str(points[0][0]))}</text><text x="530" y="260">{escape(str(points[-1][0]))}</text></svg></figure>')


def candle_chart(candles, fills, symbol, base):
    if not candles:
        return '<p>Sem candles elegíveis.</p>'
    low = min(c.low for c in candles); high = max(c.high for c in candles)
    spread = float(high-low) or 1
    def y(value):
        return 215-175*float(value-low)/spread
    def x(i):
        return 90+780*(i+.5)/len(candles)
    elements = []
    for i, c in enumerate(candles):
        color = '#147d64' if c.close >= c.open else '#ae3434'
        elements.append(f'<g><title>{c.open_time.isoformat()} OHLC {c.open}/{c.high}/{c.low}/{c.close} USDT/{base}; volume {c.volume} {base}</title>'
                        f'<line x1="{x(i)}" x2="{x(i)}" y1="{y(c.high)}" y2="{y(c.low)}" stroke="{color}"/>'
                        f'<rect x="{x(i)-12}" y="{min(y(c.open), y(c.close))}" width="24" height="{max(1,abs(y(c.open)-y(c.close)))}" fill="{color}"/></g>')
    # Cada fill é associado ao lote, inclusive vários fills no mesmo timestamp.
    for j, f in enumerate(fills):
        if f['symbol'] != symbol:
            continue
        i = next((i for i,c in enumerate(candles) if c.open_time == f['at']), len(candles)-1)
        label = f"{f['strategy_id']} {f['side']} · {f['lot_id']} · seq {f['seq']}"
        elements.append(f'<g><title>{escape(label)}</title><circle cx="{x(i)+(j%3)*6}" cy="{y(f["effective_price"])}" r="5" fill="#773ab0"/>'
                        f'<text x="{x(i)-30}" y="{25+(j%4)*16}" font-size="10">{escape(f["strategy_id"]+" "+f["side"])}</text></g>')
    for buy in fills:
        if buy['symbol'] != symbol or buy['side'] != 'BUY':
            continue
        sell = next((f for f in fills if f['lot_id'] == buy['lot_id'] and f['side'] == 'SELL'), None)
        if sell:
            start = next((i for i,c in enumerate(candles) if c.open_time == buy['at']), len(candles)-1)
            end = next((i for i,c in enumerate(candles) if c.open_time == sell['at']), len(candles)-1)
            elements.append(f'<line x1="{x(start)}" y1="{y(buy["effective_price"])}" x2="{x(end)}" y2="{y(sell["effective_price"])}" stroke="#773ab0" stroke-dasharray="5 3"><title>{escape(buy["lot_id"])}</title></line>')
    return (f'<figure><figcaption>{symbol} — candles e execuções por lote · preços USDT/{base}; volume {base}</figcaption>'
            f'<svg role="img" aria-label="Candles {symbol}" viewBox="0 0 940 265"><text x="0" y="25">{high}</text><text x="0" y="235">{low}</text>'
            +''.join(elements)+f'<text x="90" y="260">{candles[0].open_time.isoformat()}</text></svg></figure>')


def shared_html(summary):
    body = [f'<h1>ReplayQuant — carteira compartilhada</h1><p>Estado: {escape(summary["status"])} · Código {summary["exit_code"]}</p>',
            '<p>Um capital global em USDT. Contribuições usam o capital global inicial; retornos próprios têm denominadores distintos.</p>',
            _chart([(p['at'],p['gross_equity']) for p in summary['equity']], 'Patrimônio global', 'USDT')]
    for owner in summary['config'].strategies:
        body.append(_chart([(p['at'],p['equity']) for p in summary['contributions'] if p['strategy_id'] == owner.id],
                           owner.id+' — parcela do patrimônio global', 'USDT'))
    for symbol, candles in summary['candles'].items():
        base = symbol[:-4]
        body.append(candle_chart(candles, summary['fills'], symbol, base))
        for owner in summary['config'].strategies:
            if symbol not in owner.symbols:
                continue
            evaluations = [e for e in summary['evaluations'] if (e['strategy_id'],e['symbol']) == (owner.id,symbol)]
            keys = ('rsi',) if owner.strategy.name == 'RSI_REVERSION' else ('short','long')
            for key in keys:
                points = [(e['at'],Decimal(e['evaluation'][key]['value'])) for e in evaluations if e['evaluation'].get(key) is not None]
                body.append(_chart(points, owner.id+' / '+symbol+' / '+key,
                                   'pontos RSI' if key == 'rsi' else 'USDT/'+base))
    for title, headers, rows in _tables(summary):
        body.append('<h2>'+escape(title)+'</h2><div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+
                    '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v) if v is not None else '—')+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>')
    body += ['<h2>Fórmulas e limitações</h2><p>P = C + Σ Q × marca = C_UNALLOCATED + Σ P_i. PnL_i = P_i − A_i = realizado + não realizado. Contribuição_i = PnL_i / capital_global × 100. Reservas integram os saldos totais.</p>',
             '<ul>'+''.join('<li>'+escape(v)+'</li>' for v in summary['limitations'])+'</ul>',
             '<details><summary>Curva global e exposição auditável</summary><pre>'+escape(json_text(dict(equity=summary['equity'], exposure=summary['exposure'])))+'</pre></details>']
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ReplayQuant — Sprint 12</title><style>body{font:15px system-ui;overflow-wrap:anywhere;color:#183448;background:#f6f8fa;margin:0;padding:24px;line-height:1.5}main{max-width:1280px;margin:auto}h1,h2{line-height:1.2}h2{margin-top:2rem}figure{margin:16px 0;background:white;padding:12px;border:1px solid #ced8df}svg{width:100%;height:auto}text{fill:#183448;font:11px system-ui}.scroll{overflow:auto;max-width:100%;background:white}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:8px;text-align:left;border:1px solid #ced8df;vertical-align:top;overflow-wrap:anywhere;min-width:75px}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{max-width:100%}@media(max-width:500px){body{padding:12px}h1{font-size:24px}}@media print{body{padding:0;background:white;font-size:10pt}.scroll{overflow:visible}table{table-layout:fixed;font-size:7pt}th,td{min-width:0;padding:3px}figure{break-inside:avoid}details{display:none}}</style><main>'+''.join(body)+'</main></html>\n')


def _csv(rows, headers):
    flattened = []
    for row in rows:
        row = wire(row)
        flattened.append({k: canonical(v).decode() if isinstance(v, (dict,list)) else v for k,v in row.items()})
    return csv_text(headers, flattened)


def write_shared(path, metadata, summary):
    """Diretório exclusivo; qualquer falha conserva marcador INCOMPLETE."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    marker = path/'INCOMPLETE'
    marker.write_text('Exportação incompleta\n', encoding='utf-8')
    files = {'report.json': json_text(summary), 'report.md': shared_markdown(summary)}
    for name in ('events', 'ledger', 'reservations', 'risk'):
        files[name+'.jsonl'] = ''.join(canonical(r).decode()+'\n' for r in summary[name])
    projections = {
        'equity': (summary['equity'], ['seq','at','phase','reason','cash_total','cash_available','cash_reserved','gross_equity','hypothetical_liquidation_equity','paid_fees','assets','committed_exposure','open_planned_risk','exposure_excess','open_risk_excess']),
        'trades': (summary['trades'], ['trade_id','lot_id','strategy_id','symbol','quantity','buy_at','sell_at','cash_outflow','cash_inflow','net_pnl','buy_fee','sell_fee','duration_seconds','reason']),
        'allocations': (summary['allocations'], ['strategy_id','initial_allocation','cash_total','cash_available','cash_reserved','equity','pnl','contribution_pct','own_return_pct']),
        'lots': (summary['lots'], ['lot_id','strategy_id','symbol','base_asset','quantity','entry_order','entry_fill','entry_at','entry_reference','entry_price','cost_basis','stop','target','planned_loss','initial_planned_loss','status','protection_status','exit_at','exit_fill','exit_reason','realized_pnl']),
        'contributions': (summary['contributions'], ['seq','at','phase','strategy_id','initial_allocation','cash_total','cash_reserved','equity','pnl','realized_pnl','unrealized_pnl','contribution_pct','own_return_pct']),
        'exposure': (summary['exposure'], ['seq','at','phase','strategy_id','symbol','base_asset','position_notional','committed_exposure','planned_loss','portfolio_fraction']),
        'benchmarks': (summary['benchmarks'], ['portfolio','initial_cash','cash','paid_fees','gross_equity','hypothetical_liquidation_equity','return_pct','reason','observation_start','observed_until','positions','entries']),
        'metrics': ([dict(metric=k,value=v) for k,v in summary['metrics'].items()], ['metric','value'])}
    for name, (rows, headers) in projections.items():
        identity = dict(schema_version=7, run_id=summary['run_id'], quote_asset='USDT')
        files[name+'.csv'] = _csv([{**identity, **r} for r in rows], list(identity)+headers)
    for name, text in files.items():
        (path/name).write_text(text, encoding='utf-8')
    (path/'manifest.json').write_text(json_text(metadata), encoding='utf-8')
    marker.unlink()
