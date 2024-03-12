from django.urls import include, re_path

from .v1.router import v1_urlpatterns


urlpatterns = [
    re_path(r"^api/v1/", include(v1_urlpatterns)),
]
