from .base import *
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "scidas"

PRODUCT_SETTINGS = ProductSettings(
    brand="scidas",
    title="SciDAS",
    logo_url="/static/images/scidas/logo.png",
    color_scheme=ProductColorScheme("#191348", "#0079bc"),
    links=None,
)
