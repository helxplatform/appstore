from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "restartr"

PRODUCT_SETTINGS = ProductSettings(
    brand="restartr",
    title="Restarting Research",
    logo_url="/static/images/restartr/logo.png",
    color_scheme=ProductColorScheme("#ff6320", "#ffd220"),
    links=None,
)