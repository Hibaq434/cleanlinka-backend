from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='admin-dashboard'),
    path('collectors/', views.collector_list, name='admin-collector-list'),
    path('collectors/<int:pk>/', views.collector_detail, name='admin-collector-detail'),
    path('collectors/<int:pk>/verify/', views.verify_collector, name='admin-verify-collector'),
    path('collectors/<int:pk>/toggle-status/', views.toggle_collector_status, name='admin-toggle-collector-status'),
    path('jobs/', views.job_list, name='admin-job-list'),
    path('jobs/<int:pk>/', views.job_detail, name='admin-job-detail'),
    path('jobs/<int:pk>/assign/', views.assign_job, name='admin-assign-job'),
    path('users/', views.user_list, name='admin-user-list'),
    path('zones/', views.zone_list, name='admin-zone-list'),
    path('reports/', views.reports, name='admin-reports'),
    path('reports/<int:pk>/resolve/', views.resolve_report, name='admin-resolve-report'),
]