from django.urls import path, re_path

from .views import FrontendView, ReactView

urlpatterns = [
    path("frontend/", FrontendView.as_view(), name="frontend"),
    path("frontend/react/", ReactView.as_view(), name="frontend-react"),
    # Add wildcard so that a user can hit refresh in the browser and not get a 404
    re_path(r"frontend/react/*", ReactView.as_view()),
]