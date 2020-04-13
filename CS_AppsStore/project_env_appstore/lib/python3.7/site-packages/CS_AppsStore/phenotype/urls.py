from django.conf.urls import url
from phenotype import views

urlpatterns = [
    url(r'^$', views.phenotype_analyze, name="phenotype_analyze"),
]
