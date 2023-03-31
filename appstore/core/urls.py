from django.urls import path
from .views import auth,index

urlpatterns = [
    path('default/', index, name='index'),
    path("auth/", auth, name="auth"),
]
