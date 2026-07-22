from django.urls import re_path
from rest_framework.routers import DefaultRouter
from .views import (
    AppViewSet,
    InstanceViewSet,
    UsersViewSet,
    LoginProviderViewSet,
    AppContextViewSet,
    private_route,
)

router = DefaultRouter()
router.register(r"apps", AppViewSet, basename="apps")
router.register(r"providers", LoginProviderViewSet, basename="providers")
router.register(r"instances", InstanceViewSet, basename="instances")
router.register(r"users", UsersViewSet, basename="users")
router.register(r"context", AppContextViewSet, basename="context")

# Internal resolver used by the reverse proxy to route /private/... requests
# to launched-app backends (replaces the per-app Ambassador Mapping).
v1_urlpatterns = router.urls + [
    re_path(r"^private-route/?$", private_route, name="private-route"),
]
