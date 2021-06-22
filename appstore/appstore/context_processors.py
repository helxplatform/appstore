from django.conf import settings


def global_settings(request):
    """
    Manipulates the global context on any template render.
    """
    return {'APPLICATION_BRAND': settings.APPLICATION_BRAND,
            'ALLOW_DJANGO_LOGIN': settings.ALLOW_DJANGO_LOGIN,
            'ALLOW_SAML_LOGIN': settings.ALLOW_SAML_LOGIN,
            'IMAGE_DOWNLOAD_URL': settings.IMAGE_DOWNLOAD_URL,
            'DEBUG': settings.DEBUG}
