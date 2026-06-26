from models import Product


def line_total(product: Product, quantity: int) -> float:
    return product.price * quantity
