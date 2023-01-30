from .base import *
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "argus"

PRODUCT_SETTINGS = ProductSettings(
    brand="argus",
    title="Argus Array",
    logo_url="/static/images/argus/logo.png",
    color_scheme=ProductColorScheme("#8a5a91", "#505057"),
    links=None,
)
