from django.conf.urls import url
from django.urls import include

from .v1.router import v1_urlpatterns


urlpatterns = [
    url(r"^api/v1/", include(v1_urlpatterns)),
]
