from django.urls import path

from .views import FrontendView, ReactView

urlpatterns = [
    path("frontend/", FrontendView.as_view(), name="frontend"),
    path("frontend/react", ReactView.as_view(), name="frontend-react"),
]