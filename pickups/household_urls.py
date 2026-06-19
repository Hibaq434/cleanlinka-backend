from django.urls import path
from . import views

urlpatterns = [
    path('requests/', views.household_requests, name='household-requests'),
    path('requests/<int:pk>/', views.request_detail, name='household-request-detail'),
    path('requests/<int:pk>/timeline/', views.request_timeline, name='household-request-timeline'),
]