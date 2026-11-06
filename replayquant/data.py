"""Leitura de snapshots de arquivos e validação integral anterior ao replay."""
from dataclasses import dataclass, fields as dataclass_fields
from hashlib import sha256
from pathlib import Path
from .models import Candle, Config, Request
from .validation import ValidationError, fields, version, strict_json, decimal_text, datetime_text


def validate_series(candles):
    if type(candles) not in (list, tuple) or not candles:
        raise ValidationError("candles deve ser lista/tupla não vazia")
    seen, accepted, diagnostics = {}, [], []
    for index, candle in enumerate(candles):
        if not isinstance(candle, Candle):
            raise ValidationError("candles deve conter Candle")
        if candle.key in seen:
            if seen[candle.key] != candle:
                raise ValidationError("Candle conflitante na mesma chave")
            diagnostics.append({"reason": "DUPLICATE_CANDLE", "index": index})
            continue
        if accepted and candle.open_time != accepted[-1].close_time:
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


def parse_candles(raw):
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
    return validate_series(result)


def parse_config(raw):
    envelope = strict_json(raw)
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
    config: Config
    diagnostics: tuple[dict, ...]
    data_hash: str
    config_hash: str


def load_inputs(data_path, config_path):
    # Os mesmos bytes alimentam parser e hash, evitando releitura inconsistente.
    data_raw = Path(data_path).read_bytes()
    config_raw = Path(config_path).read_bytes()
    candles, diagnostics = parse_candles(data_raw)
    config = parse_config(config_raw)
    validate_schedule(candles, config)
    return Inputs(candles, config, diagnostics, sha256(data_raw).hexdigest(),
                  sha256(config_raw).hexdigest())
