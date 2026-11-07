"""Preço de abertura e custo de um preenchimento total fictício."""
from decimal import Decimal
from .models import Fill, Opening, Request, side_value
from .validation import ValidationError, decimal_value, financial


@financial
def amounts(price: Decimal, quantity: Decimal, fee_rate: Decimal):
    decimal_value(price, "price", positive=True)
    decimal_value(quantity, "quantity", positive=True)
    decimal_value(fee_rate, "fee_rate")
    if fee_rate >= 1:
        raise ValidationError("Taxa deve ser menor que 1")
    gross = price * quantity
    fee = gross * fee_rate
    return gross, fee


def make_fill(request: Request, opening: Opening, quantity: Decimal, fee_rate: Decimal):
    if not isinstance(request, Request) or not isinstance(opening, Opening):
        raise ValidationError("Preenchimento exige Request e Opening")
    _, fee = amounts(opening.price, quantity, fee_rate)
    return Fill(f"{request.id}:fill:1", request.id, request.side, quantity, opening.price, fee, opening.at)


@financial
def effective_price(reference, side, slippage_rate):
    side_value(side)
    decimal_value(reference, "reference", positive=True)
    decimal_value(slippage_rate, "slippage_rate")
    if slippage_rate >= 1:
        raise ValidationError("Slippage exige [0, 1)")
    return reference * (1 + slippage_rate if side == "BUY" else 1 - slippage_rate)


@financial
def make_sma_fill(request, opening, quantity, fee_rate, slippage_rate):
    if not isinstance(request, Request) or not isinstance(opening, Opening):
        raise ValidationError("Preenchimento exige Request e Opening")
    decimal_value(quantity, "quantity", positive=True)
    decimal_value(fee_rate, "fee_rate")
    if fee_rate >= 1:
        raise ValidationError("Taxa deve ser menor que 1")
    price = effective_price(opening.price, request.side, slippage_rate)
    # Preços derivados não herdam limites de representação das entradas.
    gross = price * quantity
    return Fill(f"{request.id}:fill:1", request.id, request.side, quantity,
                price, gross * fee_rate, opening.at)
