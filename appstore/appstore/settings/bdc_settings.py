from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "bdc"

PRODUCT_SETTINGS = ProductSettings(
    brand="bdc",
    title="Biodata Catalyst",
    logo_url="/static/images/bdc/logo.png",
    color_scheme=ProductColorScheme("#b33243", "#606264"),
    links=None,
)
