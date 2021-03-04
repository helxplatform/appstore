from rest_framework.routers import DefaultRouter
from .views import AppViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='services')
router.register(r'apps', AppViewSet, basename='apps')

v1_urlpatterns = router.urls
