from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "tracs"

PRODUCT_SETTINGS = ProductSettings(
    brand="tracs",
    title="TraCS",
    logo_url="/static/images/tracs/logo.png",
    color_scheme=ProductColorScheme("#191348", "#0079bc"),
    links=None,
)