"""Validação estrita e aritmética isolada do contexto decimal do chamador."""
from datetime import datetime, timezone
from decimal import Context, Decimal, DecimalException, Inexact, ROUND_HALF_EVEN, localcontext
from functools import wraps
import json
import re


class ValidationError(ValueError):
    """Entrada, combinação de registros ou operação aritmética inválida."""


def financial(function):
    """Toda operação financeira deve ser exata em um contexto novo."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        context = Context(prec=40, rounding=ROUND_HALF_EVEN)
        context.traps[Inexact] = True
        try:
            with localcontext(context):
                return function(*args, **kwargs)
        except DecimalException as exc:
            raise ValidationError("Aritmética financeira não representável exatamente") from exc
    return wrapped


def decimal_value(value, name, *, positive=False, bounded=True):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationError(f"{name}: esperado Decimal finito")
    if value < 0 or (positive and value == 0):
        raise ValidationError(f"{name}: valor fora da faixa permitida")
    if bounded and (len(value.as_tuple().digits) > 18 or abs(value.as_tuple().exponent) > 12):
        raise ValidationError(f"{name}: excede 18 dígitos ou expoente absoluto 12")
    return value


def decimal_text(value, name):
    if type(value) is not str or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None:
        raise ValidationError(f"{name}: esperado texto decimal com ponto, sem expoente")
    return decimal_value(Decimal(value), name)


def utc(value, name="horário"):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{name}: data deve conter fuso")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{name}: data fora da faixa UTC") from exc


def datetime_text(value, name):
    if type(value) is not str:
        raise ValidationError(f"{name}: esperado texto ISO 8601")
    try:
        return utc(datetime.fromisoformat(value), name)
    except ValueError as exc:
        raise ValidationError(f"{name}: data inválida ou sem fuso") from exc


def identifier(value, name="id"):
    if type(value) is not str or not value or value.strip() != value:
        raise ValidationError(f"{name}: texto não vazio e sem espaços nas extremidades")
    return value


def fields(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ValidationError(f"{name}: campos exigidos: {', '.join(sorted(expected))}")


def version(value):
    if type(value) is not int or value != 1:
        raise ValidationError("schema_version deve ser inteiro 1")


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValidationError(f"Chave JSON duplicada: {key}")
            obj[key] = value
        return obj

    def constant(value):
        raise ValidationError(f"Constante JSON não permitida: {value}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValidationError(f"JSON inválido: {exc}") from exc
