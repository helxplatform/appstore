from django.urls import path

from .views import (
    auth,
    login_whitelist,
)

urlpatterns = [
    path("auth/", auth, name="auth"),
    path("login_whitelist/", login_whitelist, name="login-whitelist-view"),
]
