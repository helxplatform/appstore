from .base import *
from product.configuration import ProductSettings, ProductColorScheme

# TODO remove Application brand once the new frontend is complete and
# the django templates in core are removed.
APPLICATION_BRAND = "eduhelx-chip690"

PRODUCT_SETTINGS = ProductSettings(
  brand="eduhelx-chip690",
  title="EduHeLx CHIP690",
  logo_url="/static/images/eduhelx/logo.png",
  color_scheme=ProductColorScheme("#666666", "#e6e6e6"), #TBD
  links=[],
)
