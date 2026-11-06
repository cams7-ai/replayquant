"""Preço de abertura e custo de um preenchimento total fictício."""
from decimal import Decimal
from .models import Fill, Opening, Request
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
