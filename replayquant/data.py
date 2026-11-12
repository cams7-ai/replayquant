"""Leitura de snapshots de arquivos e validação integral anterior ao replay."""
from dataclasses import dataclass, fields as dataclass_fields
from hashlib import sha256
from pathlib import Path
from .models import Candle, Config, Request, SMAConfig, SMAParameters
from .strategy_models import StrategySpec, CrossParameters, RSIParameters
from .risk_models import RiskConfig, RiskRequest, InstrumentFilters, RiskParameters
from .validation import ValidationError, fields, version, strict_json, decimal_text, datetime_text


def validate_series(candles, *, contiguous=True):
    if type(candles) not in (list, tuple) or not candles:
        raise ValidationError("candles deve ser lista/tupla não vazia")
    seen, accepted, diagnostics = {}, [], []
    for index, candle in enumerate(candles):
        if not isinstance(candle, Candle):
            raise ValidationError("candles deve conter Candle")
        if candle.key in seen:
            if seen[candle.key] != candle:
                raise ValidationError("Candle conflitante na mesma chave")
            diagnostic = {"reason": "DUPLICATE_CANDLE", "index": index}
            if not contiguous:
                # Diagnosticar na fronteira já disponível quando a repetição chegou,
                # sem deslocar avaliações passadas por uma duplicata no sufixo.
                diagnostic["at"] = accepted[-1].close_time
            diagnostics.append(diagnostic)
            continue
        if accepted and (candle.open_time <= accepted[-1].open_time
                         or (contiguous and candle.open_time != accepted[-1].close_time)):
            raise ValidationError("Candles fora de ordem ou com lacuna")
        seen[candle.key] = candle
        accepted.append(candle)
    return tuple(accepted), tuple(diagnostics)


def validate_schedule(candles, config):
    if not isinstance(config, Config):
        raise ValidationError("Configuração deve ser Config")
    closes = {c.close_time for c in candles}
    if any(r.at_close not in closes for r in config.orders):
        raise ValidationError("at_close deve referenciar fechamento existente")


def parse_candles(raw, *, contiguous=True):
    envelope = strict_json(raw)
    fields(envelope, {"schema_version", "candles"}, "dados")
    version(envelope["schema_version"])
    if type(envelope["candles"]) is not list:
        raise ValidationError("candles deve ser lista")
    result = []
    for item in envelope["candles"]:
        fields(item, {f.name for f in dataclass_fields(Candle)}, "candle")
        values = dict(item)
        for name in ("open_time", "close_time"):
            values[name] = datetime_text(values[name], name)
        for name in ("open", "high", "low", "close", "volume"):
            values[name] = decimal_text(values[name], name)
        result.append(Candle(**values))
    return validate_series(result, contiguous=contiguous)


def parse_config(raw):
    envelope = strict_json(raw)
    if type(envelope) is not dict or type(envelope.get("schema_version")) is not int:
        raise ValidationError("schema_version exige inteiro 1, 2, 4 ou 5")
    if envelope["schema_version"] in (4, 5):
        return parse_risk_config(envelope)
    if envelope["schema_version"] == 2:
        names = {f.name for f in dataclass_fields(SMAConfig)}
        fields(envelope, names | {"schema_version"}, "configuração SMA")
        values = {name: envelope[name] for name in names}
        for name in ("initial_cash", "quantity", "fee_rate", "slippage_rate"):
            values[name] = decimal_text(values[name], name)
        fields(values["strategy"], {"name", "short_window", "long_window"}, "strategy")
        values["strategy"] = SMAParameters(**values["strategy"])
        return SMAConfig(**values)
    names = {f.name for f in dataclass_fields(Config)}
    fields(envelope, names | {"schema_version"}, "configuração")
    version(envelope["schema_version"])
    values = {name: envelope[name] for name in names}
    for name in ("initial_cash", "quantity", "fee_rate", "slippage_rate"):
        values[name] = decimal_text(values[name], name)
    if type(values["orders"]) is not list:
        raise ValidationError("orders deve ser lista")
    orders = []
    for item in values["orders"]:
        fields(item, {"id", "at_close", "side"}, "ordem")
        orders.append(Request(item["id"], datetime_text(item["at_close"], "at_close"), item["side"]))
    values["orders"] = tuple(orders)
    return Config(**values)


@dataclass(frozen=True)
class Inputs:
    candles: tuple[Candle, ...]
    config: Config | SMAConfig | RiskConfig
    diagnostics: tuple[dict, ...]
    data_hash: str
    config_hash: str


def load_inputs(data_path, config_path):
    # Os mesmos bytes alimentam parser e hash, evitando releitura inconsistente.
    data_raw = Path(data_path).read_bytes()
    config_raw = Path(config_path).read_bytes()
    config = parse_config(config_raw)
    candles, diagnostics = parse_candles(data_raw, contiguous=not (isinstance(config, SMAConfig) or (isinstance(config, RiskConfig) and config.mode != 'MANUAL')))
    if isinstance(config, RiskConfig) and config.mode == 'MANUAL':
        closes = {c.close_time for c in candles}
        if any(r.at_close not in closes for r in config.orders):
            raise ValidationError('Ação deve referenciar fechamento existente')
    if isinstance(config, Config):
        validate_schedule(candles, config)
    return Inputs(candles, config, diagnostics, sha256(data_raw).hexdigest(),
                  sha256(config_raw).hexdigest())


def parse_risk_config(envelope):
    mode = envelope.get('mode')
    allowed = ('STRATEGY',) if envelope['schema_version'] == 5 else ('MANUAL', 'SMA')
    if type(mode) is not str or mode not in allowed:
        raise ValidationError('Modo incompatível com schema de configuração')
    names = {'schema_version','mode','source','symbol','interval','initial_cash','fee_rate',
             'slippage_rate','instrument_filters','risk', 'orders' if mode == 'MANUAL' else 'strategy'}
    fields(envelope, names, 'configuração de risco')
    values = {name: envelope[name] for name in names if name != 'schema_version'}
    for name in ('initial_cash', 'fee_rate', 'slippage_rate'):
        values[name] = decimal_text(values[name], name)
    for name, model in (('instrument_filters', InstrumentFilters), ('risk', RiskParameters)):
        keys = {f.name for f in dataclass_fields(model)}
        fields(values[name], keys, name)
        values[name] = model(**{k: decimal_text(v,k) for k,v in values[name].items()})
    if mode == 'SMA':
        fields(values['strategy'], {'name','short_window','long_window'}, 'strategy')
        values['strategy'] = SMAParameters(**values['strategy'])
    elif mode == 'STRATEGY':
        values['strategy'] = parse_strategy(values['strategy'])
    else:
        if type(values['orders']) is not list:
            raise ValidationError('orders exige lista')
        orders = []
        for item in values['orders']:
            cancel = isinstance(item, dict) and item.get('side') == 'CANCEL'
            keys = {'id','at_close','side'} | ({'target_order_id'} if cancel else set())
            fields(item, keys, 'ação')
            orders.append(RiskRequest(item['id'], datetime_text(item['at_close'],'at_close'),
                                      item['side'], item.get('target_order_id')))
        values['orders'] = tuple(orders)
    return RiskConfig(**values)


def parse_strategy(value):
    fields(value, {'name', 'version', 'parameters'}, 'strategy')
    name = value['name']
    if type(name) is not str or name not in ('SMA_CROSS', 'EMA_CROSS', 'RSI_REVERSION'):
        raise ValidationError('Estratégia desconhecida')
    model = RSIParameters if name == 'RSI_REVERSION' else CrossParameters
    fields(value['parameters'], {f.name for f in dataclass_fields(model)}, 'parameters')
    parameters = dict(value['parameters'])
    if model is RSIParameters:
        for key in ('oversold', 'overbought'):
            parameters[key] = decimal_text(parameters[key], key)
    return StrategySpec(name, value['version'], model(**parameters))
