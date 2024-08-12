from .base import *
from product.configuration import ProductSettings, ProductColorScheme, ProductLink

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "eduhelx-dev-student"

PRODUCT_SETTINGS = ProductSettings(
    brand="eduhelx-dev-student",
    title="EduHeLx Dev Student",
    logo_url="/static/images/eduhelx-dev-student/logo.png",
    color_scheme=ProductColorScheme("#666666", "#e6e6e6"), #TBD
    links=[],
)
