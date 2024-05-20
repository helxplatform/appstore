from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "heal"

PRODUCT_SETTINGS = ProductSettings(
    brand="heal",
    title="NIH HEAL Initiative",
    logo_url="/static/images/heal/logo.png",
    color_scheme=ProductColorScheme("#8a5a91", "#505057"),
    links=[],
)
