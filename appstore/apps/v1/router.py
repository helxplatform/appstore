from rest_framework.routers import DefaultRouter
from .views import AppViewSet, ServiceViewSet, UsersViewSet

router = DefaultRouter()
router.register(r'apps', AppViewSet, basename='apps')
router.register(r'services', ServiceViewSet, basename='services')
router.register(r'users', UsersViewSet, basename='users')

v1_urlpatterns = router.urls
