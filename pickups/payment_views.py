from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import PickupRequest, Payment, RequestEvent


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_summary(request):
    payments = Payment.objects.filter(household=request.user)

    total_paid = sum(
        p.amount for p in payments.filter(status='PAID')
    )
    total_pending = sum(
        p.amount for p in payments.filter(status='PENDING')
    )

    return Response({
        'total_paid': str(total_paid),
        'total_pending': str(total_pending),
        'total_transactions': payments.count(),
        'paid_count': payments.filter(status='PAID').count(),
        'pending_count': payments.filter(status='PENDING').count(),
        'failed_count': payments.filter(status='FAILED').count(),
    }, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_transactions(request):
    payments = Payment.objects.filter(
        household=request.user
    ).select_related('request').order_by('-created_at')

    data = [
        {
            'id': p.id,
            'request_id': p.request.id,
            'amount': str(p.amount),
            'method': p.method,
            'status': p.status,
            'reference': p.reference,
            'paid_at': p.paid_at,
            'created_at': p.created_at,
            'address': p.request.location.address_text if hasattr(p.request, 'location') else None,
            'waste_type': p.request.waste_type,
        }
        for p in payments
    ]

    return Response(data, status=status.HTTP_200_OK)