from django.urls import path

from .views import spa

urlpatterns = [
    path("spa/", spa, name="spa")
]