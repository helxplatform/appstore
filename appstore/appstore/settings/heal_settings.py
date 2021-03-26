from .base import *
from .product import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "heal"

PRODUCT_SETTINGS = ProductSettings(
    brand="heal",
    title="NIH HEAL Initiative",
    logo_url="/static/images/heal/heal-social-logo.png",
    color_scheme=ProductColorScheme("#8a5a91", "#505057"),
    links=None,
)
