from django.urls import path
from .views import auth

urlpatterns = [
    path("auth/", auth, name="auth"),
]
