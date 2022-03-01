from django.urls import path
from .views import (
    auth,
    login_whitelist,
)

urlpatterns = [
    path("auth/", auth, name="auth"),
]
