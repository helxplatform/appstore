from django.urls import path, re_path
from .views import auth, auth_identity, index, HandlePrivateURL404s

urlpatterns = [
    path('default/', index, name='index'),
    # Auth based on sessionid cookie
    path("auth/", auth, name="auth"),
    # Auth based on identity access token
    path("auth/identity/", auth_identity, name="auth-identity"),
    re_path(r"^private/*", HandlePrivateURL404s, name="private"),
]
