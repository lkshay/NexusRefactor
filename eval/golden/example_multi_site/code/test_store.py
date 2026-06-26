from cart import price_label
from models import Product
from pricing import line_total


def test_line_total() -> None:
    assert line_total(Product(id=1, unit_price=2.5), 4) == 10.0


def test_price_label() -> None:
    assert price_label(Product(id=1, unit_price=2.5)) == "$2.50"
