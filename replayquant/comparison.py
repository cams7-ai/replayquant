"""Matriz sequencial de sessões independentes, identificada por conteúdo."""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from html import escape
import re
from .catalog import load_catalog
from .data import Inputs, parse_candles, parse_config
from .coverage import matching
from .engine import replay
from .exports import csv_text, md_table
from .reporting import canonical, manifest, report, json_text, wire, write_artifacts
from .validation import ValidationError, fields, strict_json, version


@dataclass(frozen=True)
class MatrixInputs:
    children: tuple[tuple[str, Inputs], ...]
    recipe_hash: str

    def __post_init__(self):
        from .catalog_config import CatalogConfig
        if type(self.children) is not tuple or not self.children:
            raise ValidationError('Matriz exige filhos tipados')
        keys = set()
        for child in self.children:
            if type(child) is not tuple or len(child) != 2:
                raise ValidationError('Filho de matriz inválido')
            name, inputs = child
            if (type(name) is not str or re.fullmatch(r'[A-Za-z0-9_-]+', name) is None
                    or not isinstance(inputs, Inputs) or not isinstance(inputs.config, CatalogConfig)):
                raise ValidationError('Filho de matriz inválido')
            key = inputs.config.source, inputs.config.symbol, name
            if key in keys:
                raise ValidationError('Filho duplicado na matriz')
            keys.add(key)
        if type(self.recipe_hash) is not str or re.fullmatch(r'[0-9a-f]{64}', self.recipe_hash) is None:
            raise ValidationError('Hash da receita inválido')


def load_matrix(path):
    path = Path(path)
    raw = path.read_bytes()
    value = strict_json(raw)
    keys = {'schema_version', 'mode', 'catalog', 'source', 'interval', 'quote_asset', 'window',
            'initial_cash', 'fee_rate', 'slippage_rate', 'risk', 'datasets', 'strategies'}
    fields(value, keys, 'matriz')
    version(value['schema_version'])
    if value['mode'] != 'INDEPENDENT_MATRIX' or value['quote_asset'] != 'USDT':
        raise ValidationError('Matriz exige INDEPENDENT_MATRIX e cotação USDT')
    if type(value['catalog']) is not str or not value['catalog']:
        raise ValidationError('catalog exige caminho')
    catalog = load_catalog(path.parent / value['catalog'])
    if type(value['datasets']) is not list or not value['datasets'] or type(value['strategies']) is not list or not value['strategies']:
        raise ValidationError('datasets e strategies exigem listas não vazias')
    strategies = {}
    for row in value['strategies']:
        fields(row, {'id', 'strategy'}, 'estratégia da matriz')
        name = row['id']
        if type(name) is not str or re.fullmatch(r'[A-Za-z0-9_-]+', name) is None or name in strategies:
            raise ValidationError('ID de estratégia inválido/duplicado')
        strategies[name] = row['strategy']
    symbols = set()
    children = []
    common = {k:value[k] for k in ('source', 'interval', 'window', 'initial_cash', 'fee_rate', 'slippage_rate', 'risk')}
    for row in value['datasets']:
        fields(row, {'symbol', 'path'}, 'dataset')
        symbol = row['symbol']
        if type(symbol) is not str or symbol in symbols or type(row['path']) is not str or not row['path']:
            raise ValidationError('Dataset inválido/duplicado')
        symbols.add(symbol)
        raw_data = (path.parent / row['path']).read_bytes()
        candles, diagnostics = parse_candles(raw_data, contiguous=False, catalog=catalog)
        for name, strategy in sorted(strategies.items()):
            config = parse_config(canonical(dict(schema_version=6, mode='STRATEGY', symbol=symbol,
                                                 strategy=strategy, **common)), catalog=catalog)
            matching(candles, config)
            inputs = Inputs(candles, config, diagnostics, sha256(raw_data).hexdigest(), sha256(canonical(config)).hexdigest())
            children.append((name, inputs))
    children.sort(key=lambda item: (item[1].config.source, item[1].config.symbol, item[0]))
    return MatrixInputs(tuple(children), sha256(raw).hexdigest())


def rank(rows):
    groups = {}
    for row in rows:
        row['rank'] = None
        reason = ('INCOMPLETE_COVERAGE' if row['coverage']['status'] != 'FULL' else
                  ('RUN_NOT_COMPLETED' if row['status'] != 'COMPLETED' else
                   ('POLICY_REJECTION_OR_UNEXECUTED' if row['exit_code'] else None)))
        row['ranking_reason'] = reason
        if reason:
            continue
        group = canonical({k:row[k] for k in ('initial_cash', 'quote_asset', 'fee_rate', 'slippage_rate', 'risk',
                                              'window', 'observed_start', 'observed_until')})
        groups.setdefault(group, []).append(row)
    for key, members in groups.items():
        group_id = sha256(key).hexdigest()
        def exact_return(row):
            metric = row['metrics']['portfolio_return_pct']
            return Fraction(int(metric['numerator']), int(metric['denominator']))
        members.sort(key=lambda row: (-exact_return(row), row['symbol'], row['strategy_id']))
        previous = None
        position = 0
        for index, row in enumerate(members, 1):
            value = exact_return(row)
            if previous is None or value != previous:
                position = index
            row['rank'], row['ranking_group'] = position, group_id
            previous = value


def compare(inputs):
    if not isinstance(inputs, MatrixInputs) or not inputs.children:
        raise ValidationError('Esperado MatrixInputs não vazio')
    runs = []
    rows = []
    for strategy_id, child in sorted(inputs.children, key=lambda item: (item[1].config.source, item[1].config.symbol, item[0])):
        metadata = manifest(child)
        session = replay(child.candles, child.config, metadata['run_id'], child.diagnostics)
        summary = report(session)
        config = child.config
        rows.append(dict(strategy_id=strategy_id, strategy=config.strategy, source=config.source,
                         symbol=config.symbol, base_asset=config.base_asset, quote_asset='USDT', interval=config.interval,
                         run_id=session.run_id, initial_cash=config.initial_cash, fee_rate=config.fee_rate,
                         slippage_rate=config.slippage_rate, risk=config.risk, instrument_filters=config.instrument_filters,
                         window=config.window, coverage=summary['coverage'], status=summary['status'], exit_code=summary['exit_code'],
                         observed_start=summary['coverage']['observed_start'], observed_until=summary['coverage']['observed_until'],
                         metrics=summary['analysis']['metrics'], final_balance=session.balance,
                         warmup_candles=config.strategy.warmup_candles,
                         rejections=[dict(order_id=o.request.id, reason=o.reason) for o in session.orders if o.reason],
                         artifact_path=f'runs/{config.symbol}/{strategy_id}'))
        runs.append((strategy_id, metadata, session, summary))
    rank(rows)
    identity = dict(policy='SPRINT11_INDEPENDENT_MATRIX_V1',
                    children=[dict(strategy_id=r['strategy_id'], symbol=r['symbol'], run_id=r['run_id']) for r in rows])
    matrix_id = sha256(canonical(identity)).hexdigest()
    code = 1 if any(r['exit_code']==1 for r in rows) else (2 if any(r['exit_code']==2 for r in rows) else 0)
    summary = dict(schema_version=1, matrix_id=matrix_id, capital_policy='INDEPENDENT_CAPITAL_PER_RUN',
                   exit_code=code, rows=rows, ranking_policy='EXACT_MARKED_RETURN_FULL_COMPARABLE_RUNS')
    metadata = dict(schema_version=1, matrix_id=matrix_id, **identity, recipe_hash=inputs.recipe_hash)
    return metadata, summary, runs


HEADERS = ('Par', 'Estratégia', 'Capital USDT', 'Janela', 'Cobertura', 'Estado/código',
           'Taxa/slippage', 'Taxas USDT', 'Slippage USDT', 'Patrimônio USDT', 'Retorno %',
           'Drawdown %', 'Trades', 'Posição base', 'Ranking', 'Motivo', 'Execução')


def comparison_rows(summary):
    for row in wire(summary)['rows']:
        m = row['metrics']
        def metric(key):
            value = m[key]
            return value['value'] if value['value'] is not None else value['reason']
        yield (row['symbol'], row['strategy_id'], row['initial_cash'],
               f"{row['observed_start']} → {row['observed_until']}",
               f"{row['coverage']['status']} {row['coverage']['accepted_candles']}/{row['coverage']['expected_candles']}",
               f"{row['status']}/{row['exit_code']}", f"{row['fee_rate']}/{row['slippage_rate']}",
               metric('paid_fees'), metric('slippage_impact'), metric('final_gross_equity'),
               metric('portfolio_return_pct'), metric('max_drawdown_pct'), metric('closed_trade_count'),
               f"{row['final_balance']['asset_quantity']} {row['base_asset']}",
               row['rank'], row['ranking_reason'], row['run_id'])


def comparison_markdown(summary):
    lines = ['# ReplayQuant — Matriz independente', '', summary['matrix_id'], '',
             'INDEPENDENT_CAPITAL_PER_RUN', '', md_table(HEADERS, comparison_rows(summary)), '',
             '## Parâmetros e cobertura por execução', '']
    for row in wire(summary)['rows']:
        lines.extend([f"### {row['symbol']} / {row['strategy_id']}", '',
                      canonical(row).decode(), ''])
    return '\n'.join(lines) + '\n'


def comparison_html(summary):
    from .html_report import CSS, table
    rows = wire(summary)['rows']
    parts = ['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>ReplayQuant — Matriz independente</title><style>'+CSS+'.comparison-panel th{white-space:nowrap}@media print{.comparison-panel th{white-space:normal}}</style></head><body><main>',
             '<header><h1>Matriz de estratégias e pares</h1><p>INDEPENDENT_CAPITAL_PER_RUN</p>',
             '<p class="identity">'+escape(summary['matrix_id'])+'</p></header>',
             '<nav>'+''.join(f'<a href="#run-{index}">'+escape(row['symbol']+' / '+row['strategy_id'])+'</a>' for index,row in enumerate(rows))+'</nav>',
             '<section class="panel risk-panel comparison-panel"><h2>Comparação</h2>', table(HEADERS, comparison_rows(summary),
             'Capital independente por execução, custos, amostra e cobertura'), '</section>']
    for index, row in enumerate(rows):
        parts.extend([f'<section class="panel" id="run-{index}"><h2>'+escape(row['symbol']+' / '+row['strategy_id'])+'</h2>',
                      '<p class="identity">'+escape(row['run_id'])+'</p>',
                      table(('Parâmetro', 'Valor'), ((key, canonical(row[key]).decode()) for key in
                            ('strategy', 'risk', 'instrument_filters', 'window', 'coverage', 'rejections', 'metrics')),
                            'Condições e resultados da execução'), '</section>'])
    return ''.join(parts)+'</main></body></html>'


def write_comparison(directory, metadata, summary, runs):
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    marker = target/'INCOMPLETE'
    marker.write_text('Matriz incompleta: não consumir.\n')
    for strategy_id, child_metadata, session, child_summary in runs:
        write_artifacts(target/'runs'/session.config.symbol/strategy_id, child_metadata, session, child_summary)
    extra = ('source', 'base_asset', 'quote_asset', 'strategy', 'risk', 'instrument_filters', 'window', 'coverage', 'warmup_candles', 'rejections', 'metrics')
    csv_rows = [{**dict(zip(HEADERS, cells)), **{key:canonical(row[key]).decode() for key in extra}}
                for cells, row in zip(comparison_rows(summary), summary['rows'])]
    contents = {'comparison.json':json_text(summary),
                'comparison.csv':csv_text(list(HEADERS)+list(extra), csv_rows),
                'comparison.md':comparison_markdown(summary), 'manifest.json':json_text(metadata)}
    for name, content in contents.items():
        temporary = target/(name+'.tmp')
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
        temporary.replace(target/name)
    marker.unlink()
