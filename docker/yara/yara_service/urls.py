from django.urls import path
from scanner import views

urlpatterns = [
    path('health', views.health),
    path('scan', views.scan),
    path('reload', views.reload_rules),
]
