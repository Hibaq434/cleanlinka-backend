from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from users.models import User, CollectorProfile, NINVerification
from pickups.models import PickupRequest, Job
from .permissions import IsAdmin
from .serializers import (
    CollectorListSerializer, UserListSerializer,
    JobSerializer, AssignJobSerializer,
    CreatePickupRequestSerializer, DashboardSerializer,
    PickupRequestSerializer
)


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


@api_view(['GET'])
@permission_classes([IsAdmin])
def collector_list(request):
    collectors = User.objects.filter(
        role='COLLECTOR'
    ).select_related('collector_profile', 'nin_verification')
    serializer = CollectorListSerializer(collectors, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


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
        # FIX: Guard against missing collector_profile
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

    # FIX: Guard against missing collector_profile
    try:
        profile = collector.collector_profile
    except CollectorProfile.DoesNotExist:
        return Response(
            {'error': 'Collector profile not found. Cannot verify.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    profile.is_verified = True
    profile.save()

    try:
        nin = collector.nin_verification
        nin.status = 'VERIFIED'
        nin.reviewed_by = request.user
        nin.reviewed_at = timezone.now()
        nin.save()
    except NINVerification.DoesNotExist:
        pass

    return Response(
        {'message': f'Collector {collector.name} verified successfully.'},
        status=status.HTTP_200_OK
    )


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
            # FIX: Pass logged_by_admin via context so the serializer
            # create() method can access it (see serializers.py).
            pickup = serializer.save(logged_by_admin=request.user)
            return Response(
                PickupRequestSerializer(pickup).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdmin])
def job_detail(request, pk):
    try:
        job = Job.objects.select_related('request', 'collector', 'assigned_by').get(id=pk)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        # FIX: Use serializer for partial update instead of only patching status.
        # This respects validation and handles any writable field the frontend sends.
        serializer = JobSerializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        job.delete()
        return Response(
            {'message': 'Job deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAdmin])
def assign_job(request, pk):
    # FIX: The URL is /admin/jobs/:id/assign/ so pk refers to a Job, not a
    # PickupRequest. We look up the Job, then check its linked request.
    # If your frontend actually passes a PickupRequest ID here, switch
    # this back to PickupRequest.objects.get(id=pk) and update urls.py
    # to use a separate path like /admin/requests/:id/assign/.
    try:
        job = Job.objects.get(id=pk)
        return Response(
            {'error': 'This job already exists and is assigned'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Job.DoesNotExist:
        pass

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

        from notifications.models import Notification

        Notification.objects.create(
            user=collector,
            notification_type=Notification.NotificationType.JOB_ASSIGNED,
            title='New job assigned',
            message=f'You have a new pickup job. Check your app for details.',
            job=job,
        )
        pickup.status = 'ASSIGNED'
        pickup.save()

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAdmin])
def user_list(request):
    users = User.objects.all().order_by('-created_at')
    serializer = UserListSerializer(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdmin])
def zone_list(request):
    # FIX: Filter out null service_area values before returning
    zones = CollectorProfile.objects.filter(
        service_area__isnull=False
    ).exclude(
        service_area__exact=''
    ).values_list('service_area', flat=True).distinct()
    return Response(
        {'zones': list(zones)},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAdmin])
def reports(request):
    data = {
        'total_pickups': PickupRequest.objects.count(),
        'completed_pickups': PickupRequest.objects.filter(status='COMPLETED').count(),
        'failed_pickups': PickupRequest.objects.filter(status='FAILED').count(),
        'channel_breakdown': {
            'app': PickupRequest.objects.filter(channel='APP').count(),
            'whatsapp': PickupRequest.objects.filter(channel='WHATSAPP').count(),
            'call': PickupRequest.objects.filter(channel='CALL').count(),
            'admin_entry': PickupRequest.objects.filter(channel='ADMIN_ENTRY').count(),
        },
        'waste_type_breakdown': {
            'general': PickupRequest.objects.filter(waste_type='GENERAL').count(),
            'recyclable': PickupRequest.objects.filter(waste_type='RECYCLABLE').count(),
        }
    }
    return Response(data, status=status.HTTP_200_OK)


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

    # FIX: Only allow resolving jobs that are actually in a failed/disputed state.
    # Adjust these statuses to match your Job model's STATUS choices.
    resolvable_statuses = ['FAILED', 'DISPUTED', 'MISSED']
    if job.status not in resolvable_statuses:
        return Response(
            {'error': f'Job cannot be resolved from status "{job.status}". '
                      f'Must be one of: {resolvable_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
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