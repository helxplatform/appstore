from .base import *   # noqa: F401,F403
from product.configuration import ProductSettings, ProductColorScheme

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "eduhelx"

PRODUCT_SETTINGS = ProductSettings(
    brand="eduhelx",
    title="EduHeLx",
    logo_url="/static/images/eduhelx/logo.png",
    color_scheme=ProductColorScheme("#666666", "#e6e6e6"), #TBD
    links=[],
)
