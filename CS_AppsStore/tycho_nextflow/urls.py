from django.conf.urls import url

from tycho_nextflow import views

urlpatterns = [
    url(r'^deploy/$', views.deploy, name='nextflow_deploy'),
    url(r'^login_start/$', views.login_start, name='nextflow_login_start'),
]
