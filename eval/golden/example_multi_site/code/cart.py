from models import Product


def price_label(product: Product) -> str:
    return f"${product.price:.2f}"
