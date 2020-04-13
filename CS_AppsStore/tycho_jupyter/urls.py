from django.conf.urls import url
from tycho_jupyter import views


urlpatterns = [
    url(r'^deploy/$', views.deploy, name='jupyter_deploy'),
    url(r'^login_start/$', views.login_start, name='jupyter_login_start'),
    url(r'^start/$', views.start, name='jupyter_start'),
]
