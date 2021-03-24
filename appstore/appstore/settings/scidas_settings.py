from .base import *
from .product import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "scidas"

PRODUCT_SETTINGS = ProductSettings(
    brand="scidas",
    title="SciDAS",
    logo_url="/static/images/scidas/scidas-logo-sm.png",
    color_scheme=ProductColorScheme("#191348", "#0079bc"),
    links=None,
)
