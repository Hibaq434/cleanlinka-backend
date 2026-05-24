from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from pickups.models import PickupRequest
from .models import Location
from drf_spectacular.utils import extend_schema


@extend_schema(responses={201: None})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_location(request):
    request_id = request.data.get('request_id')
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

    if hasattr(pickup, 'location'):
        return Response(
            {'error': 'Location already exists for this request'},
            status=status.HTTP_400_BAD_REQUEST
        )

    location = Location.objects.create(
        request=pickup,
        latitude=request.data.get('latitude'),
        longitude=request.data.get('longitude'),
        address_text=request.data.get('address_text', ''),
        landmark=request.data.get('landmark', ''),
        whatsapp_pin_url=request.data.get('whatsapp_pin_url', '')
    )

    return Response({
        'id': location.id,
        'request_id': pickup.id,
        'latitude': str(location.latitude),
        'longitude': str(location.longitude),
        'address_text': location.address_text,
        'landmark': location.landmark,
        'whatsapp_pin_url': location.whatsapp_pin_url,
        'created_at': location.created_at,
    }, status=status.HTTP_201_CREATED)


@extend_schema(responses={200: None})
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def location_detail(request, request_id):
    try:
        pickup = PickupRequest.objects.get(id=request_id)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Pickup request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        location = pickup.location
    except Location.DoesNotExist:
        return Response(
            {'error': 'Location not found for this request'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        return Response({
            'id': location.id,
            'request_id': pickup.id,
            'latitude': str(location.latitude) if location.latitude else None,
            'longitude': str(location.longitude) if location.longitude else None,
            'address_text': location.address_text,
            'landmark': location.landmark,
            'whatsapp_pin_url': location.whatsapp_pin_url,
            'created_at': location.created_at,
        }, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        location.latitude = request.data.get('latitude', location.latitude)
        location.longitude = request.data.get('longitude', location.longitude)
        location.address_text = request.data.get('address_text', location.address_text)
        location.landmark = request.data.get('landmark', location.landmark)
        location.whatsapp_pin_url = request.data.get('whatsapp_pin_url', location.whatsapp_pin_url)
        location.save()

        return Response({
            'id': location.id,
            'request_id': pickup.id,
            'latitude': str(location.latitude) if location.latitude else None,
            'longitude': str(location.longitude) if location.longitude else None,
            'address_text': location.address_text,
            'landmark': location.landmark,
            'whatsapp_pin_url': location.whatsapp_pin_url,
            'created_at': location.created_at,
        }, status=status.HTTP_200_OK)