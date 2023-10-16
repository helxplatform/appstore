from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "ordrd"

PRODUCT_SETTINGS = ProductSettings(
    brand="ordrd",
    title="Ordr D",
    logo_url="/static/images/ordrd/logo.png",
    color_scheme=ProductColorScheme("#191348", "#0079bc"),
    links=None,
)
