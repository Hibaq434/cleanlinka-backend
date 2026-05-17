from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_location, name='create-location'),
    path('<int:request_id>/', views.location_detail, name='location-detail'),
]