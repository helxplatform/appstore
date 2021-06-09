from django.urls import path, re_path

from .views import HelxLoginView, HelxSpaLoaderView

urlpatterns = [
    path("helx/login/", HelxLoginView.as_view(), name="helx_login"),
    path("helx/", HelxSpaLoaderView.as_view(), name="helx"),
    # Add wildcard so that a user can hit refresh in the browser and not get a 404
    re_path(r"helx/*", HelxSpaLoaderView.as_view()),
]