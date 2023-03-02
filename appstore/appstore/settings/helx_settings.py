from .base import *
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "helx"

PRODUCT_SETTINGS = ProductSettings(
    brand="helx",
    title="HeLx",
    logo_url="/static/images/helx/logo.png",
    color_scheme=ProductColorScheme("#8a5a91", "#505057"),
    links=None,
)
