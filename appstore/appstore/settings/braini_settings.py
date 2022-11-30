from .base import *
from product.configuration import ProductSettings, ProductColorScheme, ProductLink

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "braini"

PRODUCT_SETTINGS = ProductSettings(
    brand="braini",
    title="Brain-I",
    logo_url="/static/images/braini/logo.png",
    color_scheme=ProductColorScheme("#666666", "#e6e6e6"),
    links=[ProductLink("Image Download", IMAGE_DOWNLOAD_URL)],
)