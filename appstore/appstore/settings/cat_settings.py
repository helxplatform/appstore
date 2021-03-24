from .base import *
from .product import ProductSettings, ProductColorScheme

APPLICATION_BRAND = "catalyst"

PRODUCT_SETTINGS = ProductSettings(
    brand="catalyst",
    title="Biodata Catalyst",
    logo_url="/static/images/catalyst/bdc-logo.svg",
    color_scheme=ProductColorScheme("#b33243", "#606264"),
    links=None,
)
