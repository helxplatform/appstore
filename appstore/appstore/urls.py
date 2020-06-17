from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView
from django.views.generic.base import TemplateView
from django.views.static import serve
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.views import refresh_jwt_token
from rest_framework_jwt.views import verify_jwt_token
from rest_framework_simplejwt import views as jwt_views

from core import views as app_core_views

import django_saml2_auth

admin.autodiscover()
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),

    path('saml2_auth/', include('django_saml2_auth.urls')),
    path('accounts/saml/', django_saml2_auth.views.signin),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('sign-out', RedirectView.as_view(url='/accounts/logout/'), name='sign-out'),
    path('accounts/', include('allauth.urls')),

    path('apps/', app_core_views.ApplicationManager.as_view(), name='apps'),
    path('list_pods/', app_core_views.list_services, name="list_pods_services"),
    path('login_whitelist/', app_core_views.login_whitelist, name='login-whitelist-view'),
    path('start/', app_core_views.AppStart.as_view(), name='start'),
    path('connect/', app_core_views.AppConnect.as_view(), name='connect'),
    path('probe/', app_core_views.ProbeServices.as_view(), name='probe_service'),

    path('irods/login', app_core_views.IrodsLogin.as_view(), name='irods_login'),
    path('', TemplateView.as_view(template_name='index.html')),
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),

    path('accounts/', include('allauth.urls')),
    path('api-token-auth/', obtain_jwt_token),
    path('api-token-refresh/', refresh_jwt_token),
    path('api-token-verify/', verify_jwt_token),
    path('auth/', app_core_views.auth, name='auth'),
]

urlpatterns += [
    path('api/token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += [
    re_path('static/(?P<path>.*)', serve, {'document_root': settings.STATIC_ROOT}),
]
