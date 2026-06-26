from invoice import receipt
from models import Order


def test_receipt() -> None:
    assert receipt(Order(id=1, total=9.5)) == "Total: 9.5"
