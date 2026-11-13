"""Orquestração local de importação/exportação e relatório de qualidade."""
from pathlib import Path
from html import escape
from .archive import digest
from .historical_models import load_import
from .historical_adapter import prepare
from .historical_store import commit_batch
from .reporting import canonical,json_text,wire
from .provenance import load_provenance
from .exports import md_table
from .validation import ValidationError


class ExportError(OSError):
    pass


def quality_markdown(quality):
    q=wire(quality)
    lines=['# ReplayQuant — Qualidade histórica', '',
           f"Origem: {q['source']} · Tipo: {q['dataset_kind']} · Estado: {q['status']}", '',
           f"Versão: {q.get('dataset_version','—')} · Ingestão: {q.get('ingestion_id','—')}", '',
           f"Adaptador: {q['adapter']} · Política: {q['policy']} · as_of UTC: {q['as_of']}", '',
           'Unidades: preços USDT/base, volume base; volume cotação USDT; trades contagem. Financeiro exato.', '',
           md_table(['Par','Linhas brutas','Únicas','Duplicatas','Incompletas','Selecionadas','Esperadas','Antes janela','Depois janela','Fora disponibilidade'],
                    [[s,*[row[k] for k in ('raw_rows','unique_rows','duplicates','incomplete','selected','expected','before_window','after_window','outside_availability')]] for s,row in q['instruments'].items()]), '',
           '## Arquivos e integridade', '',md_table(['Par','Membro','Unidade','SHA-256 bruto','SHA-256 checksum','Linhas','Duplicatas'],
                    [[f[k] for k in ('symbol','member','timestamp_unit','sha256','checksum_sha256','raw_rows','duplicates')] for f in q['files']]), '',
           '## Issues', '',md_table(['Motivo','Par','UTC'],[[i.get(k) for k in ('reason','symbol','open_time')] for i in q['issues']]), '',
           '## Universo e limitações', '',json_text(q['universe']), *['- '+v for v in q['limitations']]]
    return '\n'.join(lines)+'\n'


def quality_html(q):
    value=wire(q)
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v) if v is not None else '—')+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    body=['<h1>Qualidade histórica — '+escape(q['source'])+'</h1>',
          '<p>'+escape(q['dataset_kind']+' · '+q['status'])+'</p>',
          '<p>Preços USDT/base · volume base · volume cotação USDT · timestamps UTC · financeiro exato.</p>',
          '<h2>Identidade e hipóteses</h2>',
          table(['Campo','Valor'],[(key,value.get(key)) for key in ('dataset_version','ingestion_id','adapter','policy','as_of','window','universe')]),
          '<h2>Cobertura por instrumento</h2>',
          table(['Par','Brutas','Únicas','Duplicatas','Incompletas','Selecionadas','Esperadas','Exclusões antes/depois/disponibilidade'],
                [[symbol,*[row[k] for k in ('raw_rows','unique_rows','duplicates','incomplete','selected','expected')],
                  str([row[k] for k in ('before_window','after_window','outside_availability')])] for symbol,row in value['instruments'].items()]),
          '<h2>Arquivos e integridade SHA-256</h2>',
          table(['Par','Membro','Unidade','SHA-256 bruto','SHA-256 checksum','Linhas','Duplicatas'],
                [[row[k] for k in ('symbol','member','timestamp_unit','sha256','checksum_sha256','raw_rows','duplicates')] for row in value['files']]),
          '<h2>Issues de qualidade</h2>',table(['Motivo','Par','UTC'],[[i.get(k) for k in ('reason','symbol','open_time')] for i in value['issues']]),
          '<h2>Limitações</h2><ul>'+''.join('<li>'+escape(v)+'</li>' for v in q['limitations'])+'</ul>',
          '<details><summary>Registro completo de qualidade</summary><pre>'+escape(json_text(q))+'</pre></details>']
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ReplayQuant — Qualidade histórica</title><style>body{font:15px system-ui;color:#183448;padding:24px;margin:auto;max-width:1200px}pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5}h1{font-size:26px}.scroll{overflow:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border:1px solid #ccd7de;text-align:left;vertical-align:top;overflow-wrap:anywhere;min-width:65px}@media(max-width:500px){body{padding:12px}}@media print{body{padding:0;font-size:10pt}.scroll{overflow:visible}table{table-layout:fixed;font-size:8pt}td,th{min-width:0;padding:3px}}</style>'+''.join(body)+'</html>\n')


def render_quality(q,fmt):
    return {'json':json_text,'html':quality_html,'markdown':quality_markdown,'texto':quality_markdown}[fmt](q)


def recipes(config):
    common=dict(source=config.source,interval='1m',window=wire(config.window),initial_cash='1000',fee_rate='0.001',slippage_rate='0')
    risk=dict(risk_fraction='0.02',exposure_fraction='1',stop_fraction='0.5',target_fraction='0.9',daily_loss_fraction='0.9',drawdown_fraction='0.9',max_price_age_seconds='60')
    specs={name:dict(name=name.upper()+'_CROSS',version=1,parameters=dict(short_window=2,long_window=3)) for name in ('sma','ema')}
    individual=dict(schema_version=6,mode='STRATEGY',symbol='BTCUSDT',risk=risk,strategy=specs['sma'],**common)
    datasets=[dict(symbol=s,path=s+'.json',**({'manifest':'manifest.json'} if config.source=='BINANCE_SPOT' else {})) for s in sorted({r.symbol for r in config.raw_files})]
    matrix=dict(schema_version=1,mode='INDEPENDENT_MATRIX',catalog='catalog.json',quote_asset='USDT',risk=risk,
                datasets=datasets,strategies=[dict(id=k,strategy=v) for k,v in specs.items()],**common)
    portfolio=dict(schema_version=7,mode='SHARED_PORTFOLIO',catalog='catalog.json',quote_asset='USDT',signal_policy='ALLOCATED_BUDGETS_V1',
                   portfolio=dict(exposure_fraction='0.03001',max_open_risk_fraction='0.03',daily_loss_fraction='0.9',drawdown_fraction='0.9',max_price_age_seconds='60'),
                   instrument_limits={s:dict(exposure_fraction='0.8') for s in ('BTCUSDT','ETHUSDT')},datasets=datasets,
                   strategies=[dict(id=k,priority=i,allocation_fraction='0.5',symbols=[s],strategy=specs[k],risk=risk) for i,(k,s) in enumerate([('sma','BTCUSDT'),('ema','ETHUSDT')])],**common)
    return {'individual.json':individual,'matriz.json':matrix,'carteira.json':portfolio}


def export_batch(batch,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    marker=out/'INCOMPLETE';marker.write_text('Exportação incompleta\n')
    c=batch['config'];q=dict(batch['quality'],dataset_version=batch['dataset_version'],ingestion_id=batch['ingestion_id'])
    files={s+'.json':data for s,data in batch['normalized'].items()}
    files.update({'catalog.json':c.catalog_raw,'universe.json':c.universe_raw,
                  'quality.json':canonical(q)+b'\n','quality.md':quality_markdown(q).encode()})
    files.update({name:canonical(value)+b'\n' for name,value in recipes(c).items()})
    manifest=dict(schema_version=1,dataset_version=batch['dataset_version'],ingestion_id=batch['ingestion_id'],
                  logical=batch['logical'],code_hash=batch['code_hash'],source=c.source,
                  datasets={s:s+'.json' for s in batch['normalized']},files={name:digest(data) for name,data in sorted(files.items())},
                  raw_files=batch['quality']['files'],policy=batch['quality']['policy'],supersedes=c.supersedes,revision_reason=c.revision_reason)
    try:
        for name,data in files.items():(out/name).write_bytes(data)
        (out/'manifest.json').write_text(json_text(manifest),encoding='utf-8')
        marker.unlink()
    except OSError as exc:
        (out/'manifest.json').unlink(missing_ok=True)
        raise ExportError(f"EXPORT_FAILED: versão aceita {batch['dataset_version']}; ingestão {batch['ingestion_id']}; {exc}") from exc
    return q


def import_historical(config,repository,output,recipe_hash='API'):
    # Validation and exclusive output check precede acceptance. No network here.
    if Path(output).exists():raise ValidationError('Diretório de saída já existe')
    batch=prepare(config)
    commit_batch(repository,batch,recipe_hash)
    try:
        return export_batch(batch,output)
    except ExportError:
        raise
    except OSError as exc:
        raise ExportError(f"EXPORT_FAILED: versão aceita {batch['dataset_version']}; ingestão {batch['ingestion_id']}; {exc}") from exc


def import_path(path,repository,output):
    config,recipe_hash=load_import(path)
    return import_historical(config,repository,output,recipe_hash)


def validate_snapshot(path):
    provenance=load_provenance(path)
    from .validation import strict_json
    return strict_json(dict(provenance.files)['quality.json'])
