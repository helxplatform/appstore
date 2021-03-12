from rest_framework.routers import DefaultRouter
from .views import (
    AppViewSet,
    InstanceViewSet,
    UsersViewSet,
    LoginProviderViewSet,
    AppContextViewSet,
)

router = DefaultRouter()
router.register(r"apps", AppViewSet, basename="apps")
router.register(r"providers", LoginProviderViewSet, basename="providers")
router.register(r"instances", InstanceViewSet, basename="instances")
router.register(r"users", UsersViewSet, basename="users")
router.register(r"context", AppContextViewSet, basename="context")

v1_urlpatterns = router.urls
