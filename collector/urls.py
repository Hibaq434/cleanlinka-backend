from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.collector_profile, name='collector-profile'),
    path('jobs/', views.collector_jobs, name='collector-jobs'),
    path('jobs/<int:pk>/accept/', views.accept_job, name='collector-accept-job'),
    path('jobs/<int:pk>/decline/', views.decline_job, name='collector-decline-job'),
    path('jobs/<int:pk>/start/', views.start_job, name='collector-start-job'),
    path('jobs/<int:pk>/complete/', views.complete_job, name='collector-complete-job'),
    path('stats/', views.collector_stats, name='collector-stats'),
    path('notifications/', views.collector_notifications, name='collector-notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='collector-notification-read'),
]