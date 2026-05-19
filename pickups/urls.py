from django.urls import path
from . import views

urlpatterns = [
    path('requests/', views.create_pickup_request, name='create-pickup-request'),
    path('requests/my/', views.my_requests, name='my-requests'),
    path('requests/<int:pk>/', views.request_detail, name='request-detail'),
]