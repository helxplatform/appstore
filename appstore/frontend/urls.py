from django.urls import path, re_path

from .views import HelxLoginView, HelxSpaRedirectView, HelxSpaLoaderView, LoginWhitelistView

urlpatterns = [
    re_path(r"^$", HelxSpaRedirectView),
    # re_path(r"^$", HelxSpaLoaderView.as_view(), name="helx"),
    re_path(r"^helx/", HelxSpaLoaderView.as_view(), name="helx"),
    # Add wildcard so that a user can hit refresh in the browser and not get a 404
    re_path(r"^helx/*", HelxSpaLoaderView.as_view()),
    re_path("^login_whitelist/", LoginWhitelistView.as_view(), name="login-whitelist-view"),
]
