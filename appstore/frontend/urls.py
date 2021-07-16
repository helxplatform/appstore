from django.urls import path, re_path

#from .views import HelxLoginView, HelxSpaLoaderView
from .views import HelxSpaLoaderView
from mozilla_django_oidc.views import OIDCLogoutView
from mozilla_django_oidc.urls import OIDCAuthenticateClass


urlpatterns = [
    path("helx/login/",  OIDCAuthenticateClass.as_view(), name="helx_login"),
    path('helx/logout',OIDCLogoutView.as_view(),name='helx_logout'),
    path("helx/", HelxSpaLoaderView.as_view(), name="helx"),
    # Add wildcard so that a user can hit refresh in the browser and not get a 404
    re_path(r"helx/*", HelxSpaLoaderView.as_view()),
]