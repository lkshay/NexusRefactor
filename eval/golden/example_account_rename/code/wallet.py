from models import Account


def to_dollars(account: Account) -> float:
    return account.balance_cents / 100
