from django.urls import path

from .views import FrontendView

urlpatterns = [
    path('frontend/', FrontendView.as_view(), name='frontend'),
]