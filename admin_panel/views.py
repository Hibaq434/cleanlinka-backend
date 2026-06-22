from collections import Counter

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from users.location_scope import normalize_scope_value, resolve_lga, service_area_matches_lga
from users.models import AdminProfile, User, CollectorProfile, NINVerification
from pickups.models import PickupRequest, Job, RequestEvent
from pickups.serializers import HouseholdPickupRequestSerializer, parse_request_notes
from pickups.services import sync_pickup_charge_transaction
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


def _bool_from_request(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ['1', 'true', 'yes', 'on']
    return bool(value)


def _assign_pickup_to_collector(*, pickup, collector, assigned_by):
    job = Job.objects.create(
        request=pickup,
        collector=collector,
        assigned_by=assigned_by,
        status='ASSIGNED'
    )

    pickup.status = 'ASSIGNED'
    pickup.save(update_fields=['status', 'updated_at'])

    RequestEvent.objects.create(
        request=pickup,
        event_type='ASSIGNED',
        description=f'Collector {collector.name} assigned to this request'
    )

    Notification.objects.create(
        recipient=collector,
        channel=Notification.Channel.PUSH,
        event=Notification.Event.JOB_ASSIGNED,
        message='You have a new pickup job assigned. Check your app for details.',
        status=Notification.Status.PENDING,
    )

    sms_notification = Notification.objects.create(
        recipient=collector,
        channel=Notification.Channel.SMS,
        event=Notification.Event.JOB_ASSIGNED,
        message='You have a new pickup job assigned. Check your app for details.',
        status=Notification.Status.PENDING,
    )
    result = send_job_assigned_sms(collector.phone_number, collector.name)
    sms_notification.status = Notification.Status.SENT if result.get('success') else Notification.Status.FAILED
    sms_notification.save(update_fields=['status'])

    sync_pickup_charge_transaction(pickup, job)
    return job


def _pickup_scope_lga(pickup):
    parsed = parse_request_notes(pickup.notes or '')
    return resolve_lga(
        lga=parsed.get('lga'),
        area=parsed.get('area'),
    )


def _notes_scope_lga(notes):
    parsed = parse_request_notes(notes or '')
    return resolve_lga(
        lga=parsed.get('lga'),
        area=parsed.get('area'),
    )


def _collector_scope_lga(collector):
    try:
        profile = collector.collector_profile
    except CollectorProfile.DoesNotExist:
        return ''

    return resolve_lga(
        lga=profile.lga,
        area=profile.area,
        service_area=profile.service_area,
    )


def _infer_admin_profile(user):
    counts = Counter()
    labels = {}

    for pickup in PickupRequest.objects.filter(logged_by_admin=user).only('notes'):
        lga = _pickup_scope_lga(pickup)
        normalized = normalize_scope_value(lga)
        if normalized:
            counts[normalized] += 1
            labels.setdefault(normalized, lga)

    for job in Job.objects.filter(assigned_by=user).select_related('request'):
        lga = _pickup_scope_lga(job.request)
        normalized = normalize_scope_value(lga)
        if normalized:
            counts[normalized] += 1
            labels.setdefault(normalized, lga)

    for collector in User.objects.filter(role='COLLECTOR').select_related('collector_profile'):
        try:
            profile = collector.collector_profile
        except CollectorProfile.DoesNotExist:
            continue
        if profile.reviewed_by_id != user.id:
            continue
        lga = resolve_lga(lga=profile.lga, area=profile.area, service_area=profile.service_area)
        normalized = normalize_scope_value(lga)
        if normalized:
            counts[normalized] += 1
            labels.setdefault(normalized, lga)

    if not counts:
        return None

    normalized_lga, _ = counts.most_common(1)[0]
    return AdminProfile.objects.create(
        user=user,
        state='Lagos',
        lga=labels.get(normalized_lga, normalized_lga.title()),
        area='',
    )


def _get_admin_profile(user):
    try:
        return user.admin_profile
    except AdminProfile.DoesNotExist:
        return _infer_admin_profile(user)


def _get_scope(request):
    profile = _get_admin_profile(request.user)
    if not profile:
        return None, Response(
            {'error': 'Admin LGA scope is not configured for this account yet.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    admin_lga = resolve_lga(lga=profile.lga, area=profile.area)
    if not admin_lga:
        return None, Response(
            {'error': 'Admin LGA scope is incomplete for this account.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return {'profile': profile, 'lga': admin_lga}, None


def _collector_in_scope(collector, admin_lga):
    collector_lga = _collector_scope_lga(collector)
    if collector_lga and normalize_scope_value(collector_lga) == normalize_scope_value(admin_lga):
        return True

    try:
        profile = collector.collector_profile
    except CollectorProfile.DoesNotExist:
        return False

    return (
        service_area_matches_lga(profile.service_area, admin_lga) or
        service_area_matches_lga(profile.area, admin_lga)
    )


def _pickup_in_scope(pickup, admin_lga):
    return normalize_scope_value(_pickup_scope_lga(pickup)) == normalize_scope_value(admin_lga)


def _scoped_collectors(scope):
    queryset = User.objects.filter(role='COLLECTOR').select_related('collector_profile', 'nin_verification')
    return [collector for collector in queryset if _collector_in_scope(collector, scope['lga'])]


def _scoped_pickups(scope):
    queryset = PickupRequest.objects.select_related('household', 'logged_by_admin').order_by('-created_at')
    return [pickup for pickup in queryset if _pickup_in_scope(pickup, scope['lga'])]


def _scoped_jobs(scope):
    queryset = Job.objects.select_related('request', 'collector', 'assigned_by').order_by('-created_at')
    return [job for job in queryset if _pickup_in_scope(job.request, scope['lga'])]


@extend_schema(responses={200: DashboardSerializer})
@api_view(['GET'])
@permission_classes([IsAdmin])
def dashboard(request):
    scope, error = _get_scope(request)
    if error:
        return error

    scoped_requests = _scoped_pickups(scope)
    scoped_collectors = _scoped_collectors(scope)
    scoped_jobs = _scoped_jobs(scope)
    scoped_household_ids = {
        pickup.household_id for pickup in scoped_requests if pickup.household_id
    }

    data = {
        'total_requests': len(scoped_requests),
        'pending_requests': sum(1 for pickup in scoped_requests if pickup.status == 'PENDING'),
        'completed_requests': sum(1 for pickup in scoped_requests if pickup.status == 'COMPLETED'),
        'failed_requests': sum(1 for pickup in scoped_requests if pickup.status == 'FAILED'),
        'total_collectors': len(scoped_collectors),
        'verified_collectors': sum(
            1 for collector in scoped_collectors
            if getattr(collector.collector_profile, 'is_verified', False)
        ),
        'active_jobs': sum(
            1 for job in scoped_jobs
            if job.status in ['ASSIGNED', 'ACCEPTED', 'ON_THE_WAY', 'PICKED_UP']
        ),
        'total_households': len(scoped_household_ids),
    }
    serializer = DashboardSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: CollectorListSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAdmin])
def collector_list(request):
    scope, error = _get_scope(request)
    if error:
        return error

    collectors = _scoped_collectors(scope)
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
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        collector = User.objects.select_related('collector_profile', 'nin_verification').get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _collector_in_scope(collector, scope['lga']):
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
        profile.area = data.get('area', profile.area or profile.service_area)
        profile.lga = resolve_lga(
            lga=data.get('lga', profile.lga),
            area=data.get('area', profile.area),
            service_area=profile.service_area,
        )
        if not profile.state and (profile.area or profile.lga):
            profile.state = 'Lagos'
        profile.is_available = data.get('is_available', profile.is_available)
        profile.save()
        serializer = CollectorListSerializer(collector)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['PATCH'])
@permission_classes([IsAdmin])
def toggle_collector_status(request, pk):
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        collector = User.objects.select_related('collector_profile').get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _collector_in_scope(collector, scope['lga']):
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        profile = collector.collector_profile
    except CollectorProfile.DoesNotExist:
        return Response(
            {'error': 'Collector profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    is_active = request.data.get('is_active')
    is_available = request.data.get('is_available', is_active)
    review_notes = request.data.get('review_notes')

    if is_active is not None:
        collector.is_active = _bool_from_request(is_active)
        collector.save(update_fields=['is_active', 'updated_at'])

    if is_available is not None:
        profile.is_available = _bool_from_request(is_available)

    if review_notes is not None:
        profile.review_notes = str(review_notes).strip()

    if is_active is not None or is_available is not None or review_notes is not None:
        profile.reviewed_by = request.user
        profile.reviewed_at = timezone.now()

    if is_active is not None and not _bool_from_request(is_active):
        profile.is_verified = False

        try:
            nin = collector.nin_verification
            nin.status = 'PENDING'
            nin.reviewed_by = request.user
            nin.reviewed_at = timezone.now()
            nin.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        except NINVerification.DoesNotExist:
            pass

    profile.save(update_fields=[
        'is_available',
        'is_verified',
        'review_notes',
        'reviewed_by',
        'reviewed_at',
        'updated_at',
    ])

    serializer = CollectorListSerializer(collector)
    return Response(serializer.data, status=status.HTTP_200_OK)
@api_view(['POST'])
@permission_classes([IsAdmin])
def verify_collector(request, pk):
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        collector = User.objects.select_related('collector_profile').get(id=pk, role='COLLECTOR')
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _collector_in_scope(collector, scope['lga']):
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

    approved = _bool_from_request(request.data.get('approved', True))
    profile.is_verified = approved
    profile.is_available = approved
    profile.review_notes = str(
        request.data.get('reason') or request.data.get('review_notes') or profile.review_notes
    ).strip()
    profile.reviewed_by = request.user
    profile.reviewed_at = timezone.now()
    profile.save(update_fields=[
        'is_verified',
        'is_available',
        'review_notes',
        'reviewed_by',
        'reviewed_at',
        'updated_at',
    ])

    collector.is_active = approved
    collector.is_verified = approved
    collector.save(update_fields=['is_active', 'is_verified', 'updated_at'])

    try:
        nin = collector.nin_verification
        nin.status = 'VERIFIED' if approved else 'PENDING'
        nin.reviewed_by = request.user
        nin.reviewed_at = timezone.now()
        nin.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    except NINVerification.DoesNotExist:
        pass

    return Response(
        {
            'message': (
                f'Collector {collector.name} verified successfully.'
                if approved else
                f'Collector {collector.name} returned to review.'
            )
        },
        status=status.HTTP_200_OK
    )


@extend_schema(responses={200: JobSerializer(many=True)})
@api_view(['GET', 'POST'])
@permission_classes([IsAdmin])
def job_list(request):
    scope, error = _get_scope(request)
    if error:
        return error

    if request.method == 'GET':
        jobs = _scoped_jobs(scope)
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'POST':
        serializer = CreatePickupRequestSerializer(data=request.data)
        if serializer.is_valid():
            pickup_notes = serializer.validated_data.get('notes', '')
            request_lga = _notes_scope_lga(pickup_notes)
            if normalize_scope_value(request_lga) != normalize_scope_value(scope['lga']):
                return Response(
                    {'lga': ['Pickup request must stay within your assigned local government.']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            pickup = serializer.save(logged_by_admin=request.user)
            return Response(
                PickupRequestSerializer(pickup).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: JobSerializer})
@api_view(['GET'])
@permission_classes([IsAdmin])
def request_list(request):
    scope, error = _get_scope(request)
    if error:
        return error

    requests = _scoped_pickups(scope)
    status_filter = request.query_params.get('status')
    if status_filter:
        requests = [pickup for pickup in requests if pickup.status == str(status_filter).upper()]

    serializer = HouseholdPickupRequestSerializer(requests, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdmin])
def job_detail(request, pk):
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        job = Job.objects.select_related(
            'request', 'collector', 'assigned_by'
        ).get(id=pk)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _pickup_in_scope(job.request, scope['lga']):
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
    scope, error = _get_scope(request)
    if error:
        return error

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
            collector = User.objects.select_related('collector_profile').get(
                id=serializer.validated_data['collector_id'],
                role='COLLECTOR'
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Collector not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        if not _collector_in_scope(collector, scope['lga']):
            return Response(
                {'collector_id': ['Collector is outside your assigned local government.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        job = _assign_pickup_to_collector(
            pickup=pickup,
            collector=collector,
            assigned_by=request.user,
        )

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: UserListSerializer(many=True)})
@api_view(['POST'])
@permission_classes([IsAdmin])
def assign_request(request, pk):
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        pickup = PickupRequest.objects.get(id=pk)
    except PickupRequest.DoesNotExist:
        return Response(
            {'error': 'Pickup request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _pickup_in_scope(pickup, scope['lga']):
        return Response(
            {'error': 'Pickup request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _pickup_in_scope(pickup, scope['lga']):
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
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        collector = User.objects.select_related('collector_profile').get(
            id=serializer.validated_data['collector_id'],
            role='COLLECTOR'
        )
    except User.DoesNotExist:
        return Response(
            {'error': 'Collector not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _collector_in_scope(collector, scope['lga']):
        return Response(
            {'collector_id': ['Collector is outside your assigned local government.']},
            status=status.HTTP_400_BAD_REQUEST
        )

    job = _assign_pickup_to_collector(
        pickup=pickup,
        collector=collector,
        assigned_by=request.user,
    )
    return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
@api_view(['GET'])
@permission_classes([IsAdmin])
def user_list(request):
    scope, error = _get_scope(request)
    if error:
        return error

    scoped_requests = _scoped_pickups(scope)
    scoped_collectors = _scoped_collectors(scope)
    household_ids = [pickup.household_id for pickup in scoped_requests if pickup.household_id]
    users = [request.user, *scoped_collectors]
    if household_ids:
        users.extend(User.objects.filter(id__in=household_ids))
    users = sorted(
        {user.id: user for user in users}.values(),
        key=lambda user: user.created_at,
        reverse=True,
    )
    serializer = UserListSerializer(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAdmin])
def zone_list(request):
    scope, error = _get_scope(request)
    if error:
        return error

    zones = sorted({
        collector.collector_profile.service_area
        for collector in _scoped_collectors(scope)
        if getattr(collector, 'collector_profile', None) and collector.collector_profile.service_area
    })
    return Response(
        {'zones': list(zones)},
        status=status.HTTP_200_OK
    )


@extend_schema(responses={200: None})
@api_view(['GET'])
@permission_classes([IsAdmin])
def reports(request):
    scope, error = _get_scope(request)
    if error:
        return error

    scoped_requests = _scoped_pickups(scope)

    data = {
        'total_pickups': len(scoped_requests),
        'completed_pickups': sum(1 for pickup in scoped_requests if pickup.status == 'COMPLETED'),
        'failed_pickups': sum(1 for pickup in scoped_requests if pickup.status == 'FAILED'),
        'channel_breakdown': {
            'app': sum(1 for pickup in scoped_requests if pickup.channel == 'APP'),
            'whatsapp': sum(1 for pickup in scoped_requests if pickup.channel == 'WHATSAPP'),
            'call': sum(1 for pickup in scoped_requests if pickup.channel == 'CALL'),
            'admin_entry': sum(1 for pickup in scoped_requests if pickup.channel == 'ADMIN_ENTRY'),
        },
        'waste_type_breakdown': {
            'general': sum(1 for pickup in scoped_requests if pickup.waste_type == 'GENERAL'),
            'recyclable': sum(1 for pickup in scoped_requests if pickup.waste_type == 'RECYCLABLE'),
        }
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(responses={200: None})
@api_view(['PATCH'])
@permission_classes([IsAdmin])
def resolve_report(request, pk):
    scope, error = _get_scope(request)
    if error:
        return error

    try:
        job = Job.objects.select_related('request').get(id=pk)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not _pickup_in_scope(job.request, scope['lga']):
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
    sync_pickup_charge_transaction(job.request, job)

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
