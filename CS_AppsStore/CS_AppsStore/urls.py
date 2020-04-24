"""CS_AppsStore URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
try:
    from django.urls import include, url
except ImportError:
    from django.conf.urls import include, url
    
#from oidc_provider import urls
from django.contrib import admin
from django.views.static import serve
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic.base import TemplateView
admin.autodiscover()
from django.contrib.auth.views import LoginView

#from django.urls import path
from rest_framework_simplejwt import views as jwt_views

#from django.urls import path
#from myapi.core import views

#urlpatterns = [
#    url(r'^AppsStore_JWT/', AppsStore_JWT.as_view(), name='AppsStore_JWT'),
#]

from apps_core_services import views
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.views import refresh_jwt_token
from rest_framework_jwt.views import verify_jwt_token


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^signout_view$', views.signout_view),
    #url(r'^', include('oidc_provider.urls', namespace='oidc_provider')),
    #url(r'^accounts/login/$', auth_views.login, {'template_name': 'login.html'}, name='login'),
    url(r'^accounts/login/$', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    url(r'^apps/$', views.show_apps, name='apps-view'),
    url(r'^login_apps/$', views.login_show_apps, name='login-apps-view'),
    url(r'^login_apps/signout_view$', views.signout_view),
    url(r'^$', TemplateView.as_view(template_name='index.html')),
    url(r'^accounts/profile/$', TemplateView.as_view(template_name='profile.html')),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^rest-auth/', include('rest_auth.urls')),
    url(r'^rest-auth/registration/', include('rest_auth.registration.urls')),
    #url(r'^$', views.home_page_view, name='home-page-view'),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^api-token-auth/', obtain_jwt_token),
    url(r'^api-token-refresh/', refresh_jwt_token),
    url(r'^api-token-verify/', verify_jwt_token),
    url(r'auth/', views.auth, name='auth'),
    url(r'test/', views.test, name='test'),
    url(r'^list_pods/$', views.list_services, name="list_pods_services"),
]

urlpatterns += [
    url('^phenotype/', include('phenotype.urls')),
    url('^tycho_jupyter/', include('tycho_jupyter.urls')),
    url('^tycho_nextflow/', include('tycho_nextflow.urls')),
    url('^cloudtop_imagej/', include('cloudtop_imagej.urls')),
#    url(r'^rest-auth/github/$', GitHubLogin.as_view(), name='github_login'),
]

#rom accounts.views import GoogleLogin
#from accounts.views import GitHubLogin

#urlpatterns += [
#    url(r"^rest-auth/github/", GitHubLogin.as_view(), name="github_login"),
#from accounts.views import GoogleLogin
#    url(r"^rest-auth/google/", GoogleLogin.as_view(), name="google_login"),
#]

#from myapi.core import views

urlpatterns += [
    #url(r'^AppsStore_JWT/', AppsStore_JWT.as_view(), name='AppsStore_JWT'),
    url(r'^api/token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    url(r'^api/token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += [
        url(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]
