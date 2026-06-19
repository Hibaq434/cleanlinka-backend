from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from users.models import User, CollectorProfile, NINVerification
from pickups.models import PickupRequest, Job, RequestEvent
from notifications.models import Notification
from notifications.sms import send_job_assigned_sms
from .permissions import IsAdmin
from .serializers import (
    CollectorListSerializer, UserListSerializer,
    JobSerializer, AssignJobSerializer,
    CreatePickupRequestSerializer, DashboardSerializer,
    PickupRequestSerializer
)
from drf_spectacular.utils import extend_schema


@extend_schema(responses={200: DashboardSerializer})
@api_view(['GET'])
@permission_classes([IsAdmin])
def dashboard(request):
    data = {
        'total_requests': PickupRequest.objects.count(),
        'pending_requests': PickupRequest.objects.filter(status='PENDING').count(),
        'completed_requests': PickupRequest.objects.filter(status='COMPLETED').count(),
        'failed_requests': PickupRequest.objects.filter(status='FAILED').count(),
        'total_collectors': User.objects.filter(role='COLLECTOR').count(),
        'verified_collectors': CollectorProfile.objects.filter(is_verified=True).count(),
        'active_jobs': Job.objects.filter(
            status__in=['ASSIGNED', 'ACCEPTED', 'ON_THE_WAY', 'PICKED_UP']
        ).count(),
        'total_households': User.objects.filter(role='HOUSEHOLD').count(),
    }
    serializer = DashboardSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: CollectorListSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAdmin])
def collector_list(request):
    collectors = User.objects.filter(
        role='COLLECTOR'
    ).select_related('collector_profile', 'nin_verification')
    serializer = CollectorListSerializer(collectors, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    methods=['GET'],
    responses={200: CollectorListSerializer}
)
@extend_schema(
    methods=['PATCH'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'vehicle_type': {'type': 'string'},
                'service_area': {'type': 'string'},
                'is_available': {'type': 'boolean'},
            }
        }
    },
    responses={200: CollectorListSerializer}
)
@api_view(['GET', 'PATCH'])
@permission_classes([IsAdmin])
def collector_detail(request, pk):
    try:
        collector = User.objects.get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        serializer = CollectorListSerializer(collector)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        try:
            profile = collector.collector_profile
        except CollectorProfile.DoesNotExist:
            return Response(
                {'error': 'Collector profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data
        profile.vehicle_type = data.get('vehicle_type', profile.vehicle_type)
        profile.service_area = data.get('service_area', profile.service_area)
        profile.is_available = data.get('is_available', profile.is_available)
        profile.save()
        serializer = CollectorListSerializer(collector)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['POST'])
@permission_classes([IsAdmin])
def verify_collector(request, pk):
    try:
        collector = User.objects.get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        profile = collector.collector_profile
    except CollectorProfile.DoesNotExist:
        return Response(
            {'error': 'Collector profile not found. Cannot verify.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    profile.is_verified = True
    profile.save()

    collector.is_active = True
    collector.save()

    try:
        nin = collector.nin_verification
        nin.status = 'VERIFIED'
        nin.reviewed_by = request.user
        nin.reviewed_at = timezone.now()
        nin.save()
    except NINVerification.DoesNotExist:
        pass

    return Response({
        'message': f'Collector {collector.name} verified successfully.',
        'is_verified': True,
        'is_active': collector.is_active,
        'status': 'active'
    }, status=status.HTTP_200_OK)


@extend_schema(responses={200: JobSerializer(many=True)})
@api_view(['GET', 'POST'])
@permission_classes([IsAdmin])
def job_list(request):
    if request.method == 'GET':
        jobs = Job.objects.select_related(
            'request', 'collector', 'assigned_by'
        ).all().order_by('-created_at')
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'POST':
        serializer = CreatePickupRequestSerializer(data=request.data)
        if serializer.is_valid():
            pickup = serializer.save(logged_by_admin=request.user)
            return Response(
                PickupRequestSerializer(pickup).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: JobSerializer})
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdmin])
def job_detail(request, pk):
    try:
        job = Job.objects.select_related(
            'request', 'collector', 'assigned_by'
        ).get(id=pk)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        new_status = request.data.get('status')
        if new_status:
            job.status = new_status
            job.save()
        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'DELETE':
        job.delete()
        return Response(
            {'message': 'Job deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


@extend_schema(request=AssignJobSerializer, responses={201: JobSerializer})
@api_view(['POST'])
@permission_classes([IsAdmin])
def assign_job(request, pk):
    try:
        pickup = PickupRequest.objects.get(id=pk)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Pickup request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if hasattr(pickup, 'job'):
        return Response(
            {'error': 'This request already has a job assigned'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = AssignJobSerializer(data=request.data)
    if serializer.is_valid():
        try:
            collector = User.objects.get(
                id=serializer.validated_data['collector_id'],
                role='COLLECTOR'
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Collector not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        job = Job.objects.create(
            request=pickup,
            collector=collector,
            assigned_by=request.user,
            status='ASSIGNED'
        )

        pickup.status = 'ASSIGNED'
        pickup.save()

        RequestEvent.objects.create(
            request=pickup,
            event_type='ASSIGNED',
            description=f'Collector {collector.name} assigned to this request'
        )

        Notification.objects.create(
            recipient=collector,
            channel='PUSH',
            event='JOB_ASSIGNED',
            message='You have a new pickup job assigned. Check your app for details.',
            status='PENDING'
        )

        sms_notification = Notification.objects.create(
            recipient=collector,
            channel=Notification.Channel.SMS,
            event=Notification.Event.JOB_ASSIGNED,
            message='You have a new pickup job assigned. Check your app for details.',
            status=Notification.Status.PENDING,
        )

        result = send_job_assigned_sms(collector.phone_number, collector.name)
        if result.get('success'):
            sms_notification.status = Notification.Status.SENT
        else:
            sms_notification.status = Notification.Status.FAILED
        sms_notification.save(update_fields=['status'])

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: UserListSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAdmin])
def user_list(request):
    users = User.objects.all().order_by('-created_at')
    serializer = UserListSerializer(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAdmin])
def zone_list(request):
    zones = CollectorProfile.objects.filter(
        service_area__isnull=False
    ).exclude(
        service_area__exact=''
    ).values_list('service_area', flat=True).distinct()
    return Response(
        {'zones': list(zones)},
        status=status.HTTP_200_OK
    )


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAdmin])
def reports(request):
    data = {
        'total_pickups': PickupRequest.objects.count(),
        'completed_pickups': PickupRequest.objects.filter(
            status='COMPLETED'
        ).count(),
        'failed_pickups': PickupRequest.objects.filter(
            status='FAILED'
        ).count(),
        'channel_breakdown': {
            'app': PickupRequest.objects.filter(channel='APP').count(),
            'whatsapp': PickupRequest.objects.filter(channel='WHATSAPP').count(),
            'call': PickupRequest.objects.filter(channel='CALL').count(),
            'admin_entry': PickupRequest.objects.filter(
                channel='ADMIN_ENTRY'
            ).count(),
        },
        'waste_type_breakdown': {
            'general': PickupRequest.objects.filter(
                waste_type='GENERAL'
            ).count(),
            'recyclable': PickupRequest.objects.filter(
                waste_type='RECYCLABLE'
            ).count(),
        }
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['PATCH'])
@permission_classes([IsAdmin])
def resolve_report(request, pk):
    try:
        job = Job.objects.get(id=pk)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    job.status = 'COMPLETED'
    job.completed_at = timezone.now()
    job.save()

    job.request.status = 'COMPLETED'
    job.request.save()

    return Response(
        {'message': 'Report resolved successfully.'},
        status=status.HTTP_200_OK
    )


@extend_schema(
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'is_active': {'type': 'boolean'},
            },
            'required': ['is_active']
        }
    },
    responses={200: None}
)
@api_view(['PATCH'])
@permission_classes([IsAdmin])
def toggle_collector_status(request, pk):
    try:
        collector = User.objects.get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response(
            {'error': 'is_active field is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    collector.is_active = is_active
    collector.save()

    try:
        collector.collector_profile.is_available = is_active
        collector.collector_profile.save()
    except Exception:
        pass

    return Response({
        'message': 'Collector status updated successfully.',
        'is_active': collector.is_active,
        'status': 'active' if is_active else 'inactive'
    }, status=status.HTTP_200_OK)
@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAdmin])
def insights_summary(request):
    from django.db.models import Count

    # Top demand areas
    top_areas = PickupRequest.objects.exclude(
        area__exact=''
    ).values('area').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # Top LGAs
    top_lgas = PickupRequest.objects.exclude(
        lga__exact=''
    ).values('lga').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # Active collector load
    from pickups.models import Job
    collector_load = Job.objects.filter(
        status__in=['ASSIGNED', 'ACCEPTED', 'ON_THE_WAY']
    ).values(
        'collector__id',
        'collector__name',
        'collector__phone_number'
    ).annotate(
        active_jobs=Count('id')
    ).order_by('-active_jobs')[:10]

    # Request counts
    total = PickupRequest.objects.count()
    completed = PickupRequest.objects.filter(status='COMPLETED').count()
    pending = PickupRequest.objects.filter(status='PENDING').count()
    assigned = PickupRequest.objects.filter(status='ASSIGNED').count()
    failed = PickupRequest.objects.filter(status='FAILED').count()

    return Response({
        'request_counts': {
            'total': total,
            'pending': pending,
            'assigned': assigned,
            'completed': completed,
            'failed': failed,
            'conversion_rate': round((completed / total * 100) if total > 0 else 0, 2),
        },
        'top_demand_areas': list(top_areas),
        'top_demand_lgas': list(top_lgas),
        'active_collector_load': list(collector_load),
        'collector_counts': {
            'total': User.objects.filter(role='COLLECTOR').count(),
            'verified': CollectorProfile.objects.filter(is_verified=True).count(),
            'active': User.objects.filter(role='COLLECTOR', is_active=True).count(),
        }
    }, status=status.HTTP_200_OK)