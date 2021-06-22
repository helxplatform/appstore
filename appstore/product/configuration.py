from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProductColorScheme:
    """
    Per product hex colors
    """

    primary: str = "#00a8c1"
    secondary: str = "#d2cbcb"


@dataclass
class ProductLink:
    """
    Per product links
    """

    title: str
    link: str


@dataclass
class ProductSettings:
    """
    Per product application settings.

    Defaults to Common Share product settings.
    """

    links: Optional[List[ProductLink]]
    brand: str = "CommonsShare"
    title: str = "CommonsShare"
    logo_url: str = "/static/images/commonsshare/logo-lg.png"
    color_scheme: ProductColorScheme = ProductColorScheme()
    capabilities: List[str] = field(default_factory=lambda: ['app', 'search'])

