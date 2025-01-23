from django.urls import path, re_path
from .views import auth, index, HandlePrivateURL404s

urlpatterns = [
    path('default/', index, name='index'),
    path("auth/", auth, name="auth"),
    re_path(r"^private/*", HandlePrivateURL404s, name="private"),
]
