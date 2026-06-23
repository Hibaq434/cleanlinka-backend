from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import PickupRequest, Payment, RequestEvent
from admin_panel.permissions import IsAdmin


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


@extend_schema(
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'request_id': {'type': 'integer'},
                'amount': {'type': 'number'},
                'method': {'type': 'string', 'enum': ['CASH', 'TRANSFER', 'CARD', 'USSD']},
                'reference': {'type': 'string'},
            },
            'required': ['request_id']
        }
    },
    responses={201: None}
)
@api_view(['POST'])
@permission_classes([IsAdmin])
def record_payment(request):
    request_id = request.data.get('request_id')
    amount = request.data.get('amount')
    method = request.data.get('method', 'CASH')
    reference = request.data.get('reference', '')

    if not request_id:
        return Response(
            {'error': 'request_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        pickup = PickupRequest.objects.get(id=request_id)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Pickup request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if hasattr(pickup, 'payment'):
        return Response(
            {'error': 'Payment already recorded for this request'},
            status=status.HTTP_400_BAD_REQUEST
        )

    amount = amount or pickup.flat_rate_price

    payment = Payment.objects.create(
        request=pickup,
        household=pickup.household,
        amount=amount,
        method=method,
        reference=reference,
        status='PAID',
        paid_at=timezone.now()
    )

    RequestEvent.objects.create(
        request=pickup,
        event_type='PAYMENT_RECORDED',
        description=f'Payment of {amount} recorded via {method}'
    )

    return Response({
        'message': 'Payment recorded successfully.',
        'payment_id': payment.id,
        'amount': str(payment.amount),
        'status': payment.status,
    }, status=status.HTTP_201_CREATED)
