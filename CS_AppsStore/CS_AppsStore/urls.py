from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView, TemplateView
from django.views.static import serve
from rest_framework_simplejwt import views as jwt_views

from apps_core_services import views as app_core_views

admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),

    path('accounts/login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('sign-out', RedirectView.as_view(url='/accounts/logout/'), name='sign-out'),
    path('accounts/', include('allauth.urls')),

    path('apps/', app_core_views.ApplicationManager.as_view(), name='apps'),
    path('list_pods/', app_core_views.list_services, name="list_pods_services"),
    path('login_whitelist/', app_core_views.login_whitelist, name='login-whitelist-view'), ]

urlpatterns += [
    path('phenotype/', include('phenotype.urls')),
    path('tycho_jupyter/', include('tycho_jupyter.urls')),
    path('tycho_nextflow/', include('tycho_nextflow.urls')),
    path('cloudtop_imagej/', include('cloudtop_imagej.urls')),
]

urlpatterns += [
    path('api/token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += [
    re_path('static/(?P<path>.*)', serve, {'document_root': settings.STATIC_ROOT}),
]
