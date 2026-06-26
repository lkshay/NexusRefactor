from models import Account
from wallet import to_dollars


def test_to_dollars() -> None:
    assert to_dollars(Account(id=1, balance_minor=250)) == 2.5
