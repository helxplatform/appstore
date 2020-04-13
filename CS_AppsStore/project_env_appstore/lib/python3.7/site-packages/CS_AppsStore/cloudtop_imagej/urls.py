from django.conf.urls import url
from cloudtop_imagej import views


urlpatterns = [
    url(r'^deploy/$', views.deploy, name='cloudtop_imagej_deploy'),
    url(r'^login_start/$', views.login_start, name='cloudtop_imagej_login_start'),
    url(r'^start/$', views.start, name='cloudtop_imagej_start'),
]
