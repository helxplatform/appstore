from .base import *
from product.configuration import ProductSettings, ProductColorScheme, ProductLink

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "eduhelx-professor"

PRODUCT_SETTINGS = ProductSettings(
    brand="eduhelx-professor",
    title="EduHeLx Professor",
    logo_url="/static/images/eduhelx/logo.png",
    color_scheme=ProductColorScheme("#666666", "#e6e6e6"), #TBD
    links=[],
)
