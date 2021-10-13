from django.urls import path

from .views import (
    ApplicationManager,
    AppStart,
    AppConnect,
    IndexView,
    ProbeServices,
    auth,
    list_services,
    login_whitelist,
)

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("apps/", ApplicationManager.as_view(), name="apps"),
    path("auth/", auth, name="auth"),
    path("connect/", AppConnect.as_view(), name="connect"),
    path("login_whitelist/", login_whitelist, name="login-whitelist-view"),
    path("probe/", ProbeServices.as_view(), name="probe_service"),
    path("start/", AppStart.as_view(), name="start"),
]