from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from apps import views

urlpatterns = [
    path('helx_apps/', views.AppView.as_view()),
    path('helx_services/', views.ServiceView.as_view()),

]