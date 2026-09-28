from django.urls import path
from . import views

app_name = 'multi_av'

urlpatterns = [
    path('scan/<int:file_id>/', views.scan_uploaded_file, name='scan_file'),
    path('status/<uuid:scan_id>/', views.scan_status, name='scan_status'),
    path('history/', views.scan_history, name='history'),
    path('history/<int:file_id>/', views.scan_history, name='history_file'),
    path('engines-status/', views.engines_status, name='engines_status'),
    path('statistics/', views.statistics, name='statistics'),
]