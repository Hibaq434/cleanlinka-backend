from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('verify-otp/', views.verify_otp, name='verify-otp'),
    path('resend-otp/', views.resend_otp, name='resend-otp'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('verify-nin/', views.verify_nin, name='verify-nin'),
    path('me/', views.me, name='me'),
]