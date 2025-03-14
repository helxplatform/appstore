from .base import *
from product.configuration import ProductSettings, ProductColorScheme, ProductLink

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "eduhelx-student"

PRODUCT_SETTINGS = ProductSettings(
    brand="eduhelx-student",
    title="EduHeLx",
    logo_url="/static/images/eduhelx-student/logo.png",
    color_scheme=ProductColorScheme("#666666", "#e6e6e6"), #TBD
    links=[],
)
