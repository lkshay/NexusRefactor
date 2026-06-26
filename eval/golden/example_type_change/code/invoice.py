from models import Order


def receipt(order: Order) -> str:
    return "Total: " + order.total
