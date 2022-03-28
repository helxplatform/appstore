from django.conf import settings
from frontend.views import get_brand_details

def global_settings(request):
    """
    Manipulates the global context on any template render.
    """
    brand_context = get_brand_details()
    brand = brand_context["brand"]
    full_brand = brand_context["title"]
    brand_logo = brand_context["logo_url"]

    return {'APPLICATION_BRAND': settings.APPLICATION_BRAND,
            'ALLOW_DJANGO_LOGIN': settings.ALLOW_DJANGO_LOGIN,
            'ALLOW_SAML_LOGIN': settings.ALLOW_SAML_LOGIN,
            'IMAGE_DOWNLOAD_URL': settings.IMAGE_DOWNLOAD_URL,
            'DEBUG': settings.DEBUG,
            'brand': brand,
            'full_brand': full_brand,
            'brand_logo': brand_logo}
