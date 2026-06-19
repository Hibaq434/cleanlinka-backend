from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PickupRequest, RequestEvent
from .serializers import (
    CreatePickupRequestSerializer,
    PickupRequestDetailSerializer,
    RequestEventSerializer
)
from notifications.sms import send_request_confirmed_sms
from notifications.models import Notification
from drf_spectacular.utils import extend_schema


@extend_schema(
    request=CreatePickupRequestSerializer,
    responses={201: PickupRequestDetailSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_pickup_request(request):
    serializer = CreatePickupRequestSerializer(data=request.data)
    if serializer.is_valid():
        pickup = serializer.save(household=request.user)

        try:
            Notification.objects.create(
                recipient=request.user,
                channel='SMS',
                event='REQUEST_RECEIVED',
                message='Your waste pickup request has been received. We will assign a collector shortly.',
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


@extend_schema(responses={200: PickupRequestDetailSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_requests(request):
    requests_qs = PickupRequest.objects.filter(
        household=request.user
    ).order_by('-created_at')
    serializer = PickupRequestDetailSerializer(requests_qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: PickupRequestDetailSerializer})
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


@extend_schema(responses={200: RequestEventSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_timeline(request, pk):
    try:
        pickup = PickupRequest.objects.get(id=pk, household=request.user)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    events = pickup.events.all()
    serializer = RequestEventSerializer(events, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    methods=['GET'],
    responses={200: PickupRequestDetailSerializer(many=True)}
)
@extend_schema(
    methods=['POST'],
    request=CreatePickupRequestSerializer,
    responses={201: PickupRequestDetailSerializer}
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def household_requests(request):
    if request.method == 'GET':
        requests_qs = PickupRequest.objects.filter(
            household=request.user
        ).order_by('-created_at')
        serializer = PickupRequestDetailSerializer(requests_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'POST':
        serializer = CreatePickupRequestSerializer(data=request.data)
        if serializer.is_valid():
            pickup = serializer.save(household=request.user)
            try:
                Notification.objects.create(
                    recipient=request.user,
                    channel='SMS',
                    event='REQUEST_RECEIVED',
                    message='Your waste pickup request has been received. We will assign a collector shortly.',
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