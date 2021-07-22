from .base import *
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "restartr"

PRODUCT_SETTINGS = ProductSettings(
    brand="restartr",
    title="Restarting Research",
    logo_url="/static/images/restartr/restartingresearch.png",
    color_scheme=ProductColorScheme("#ff6320", "#ffd220"),
    links=None,
)