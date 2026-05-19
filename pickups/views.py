from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PickupRequest
from .serializers import CreatePickupRequestSerializer, PickupRequestDetailSerializer
from notifications.sms import send_request_confirmed_sms
from notifications.models import Notification


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_pickup_request(request):
    serializer = CreatePickupRequestSerializer(data=request.data)
    if serializer.is_valid():
        pickup = serializer.save(household=request.user)

        # Send confirmation SMS to household
        try:
            Notification.objects.create(
                recipient=request.user,
                channel='SMS',
                event='REQUEST_RECEIVED',
                message=f'Your waste pickup request has been received. We will assign a collector shortly.',
                status='PENDING'
            )
            send_request_confirmed_sms(
                request.user.phone_number,
                request.user.name
            )
        except Exception as e:
            print(f"[SMS Error] {str(e)}")

        return Response(
            PickupRequestDetailSerializer(pickup).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_requests(request):
    requests_qs = PickupRequest.objects.filter(
        household=request.user
    ).order_by('-created_at')
    serializer = PickupRequestDetailSerializer(requests_qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_detail(request, pk):
    try:
        pickup = PickupRequest.objects.get(id=pk, household=request.user)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Request not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = PickupRequestDetailSerializer(pickup)
    return Response(serializer.data, status=status.HTTP_200_OK)