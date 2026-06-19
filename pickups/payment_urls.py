from django.urls import path
from . import payment_views

urlpatterns = [
    path('summary/', payment_views.payment_summary, name='payment-summary'),
    path('transactions/', payment_views.payment_transactions, name='payment-transactions'),
]