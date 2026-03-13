from django.urls import re_path

from .views import HelxSpaRedirectView, HelxSpaLoaderView, LoginWhitelistView

urlpatterns = [
    re_path(r"^$", HelxSpaRedirectView),
    re_path("^login_whitelist/", LoginWhitelistView.as_view(), name="login-whitelist-view"),
    #re_path(r"^helx/", HelxSpaLoaderView.as_view(), name="helx"),
]
