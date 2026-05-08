from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone

from users.models import CollectorProfile
from pickups.models import Job
from notifications.models import Notification
from .permissions import IsCollector
from .serializers import (
    CollectorProfileSerializer,
    CollectorJobSerializer,
    NotificationSerializer,
    CollectorStatsSerializer,
)


def _get_profile(user):
    try:
        return user.collector_profile, None
    except CollectorProfile.DoesNotExist:
        return None, Response(
            {'error': 'Collector profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET', 'PATCH'])
@permission_classes([IsCollector])
def collector_profile(request):
    profile, err = _get_profile(request.user)
    if err:
        return err

    if request.method == 'GET':
        return Response(CollectorProfileSerializer(profile).data, status=status.HTTP_200_OK)

    allowed = {'is_available', 'vehicle_type'}
    data = {k: v for k, v in request.data.items() if k in allowed}
    serializer = CollectorProfileSerializer(profile, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsCollector])
def collector_jobs(request):
    jobs = Job.objects.filter(
        collector=request.user
    ).select_related('request', 'request__household').order_by('-created_at')

    status_filter = request.query_params.get('status')
    if status_filter:
        jobs = jobs.filter(status=status_filter.upper())

    return Response(CollectorJobSerializer(jobs, many=True).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsCollector])
def accept_job(request, pk):
    try:
        job = Job.objects.select_related('request').get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if job.status != Job.Status.ASSIGNED:
        return Response(
            {'error': f'Cannot accept a job with status "{job.status}". Must be ASSIGNED.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = Job.Status.ACCEPTED
    job.accepted_at = timezone.now()
    job.save(update_fields=['status', 'accepted_at', 'updated_at'])
    return Response(CollectorJobSerializer(job).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsCollector])
def decline_job(request, pk):
    try:
        job = Job.objects.select_related('request').get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if job.status != Job.Status.ASSIGNED:
        return Response(
            {'error': f'Cannot decline a job with status "{job.status}". Must be ASSIGNED.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = Job.Status.REJECTED
    job.save(update_fields=['status', 'updated_at'])
    job.request.status = 'PENDING'
    job.request.save(update_fields=['status', 'updated_at'])
    return Response(CollectorJobSerializer(job).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsCollector])
def start_job(request, pk):
    try:
        job = Job.objects.select_related('request').get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if job.status != Job.Status.ACCEPTED:
        return Response(
            {'error': f'Cannot start a job with status "{job.status}". Must be ACCEPTED.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = Job.Status.ON_THE_WAY
    job.save(update_fields=['status', 'updated_at'])
    return Response(CollectorJobSerializer(job).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsCollector])
def complete_job(request, pk):
    try:
        job = Job.objects.select_related('request').get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    completable = [Job.Status.ON_THE_WAY, Job.Status.PICKED_UP]
    if job.status not in completable:
        return Response(
            {'error': f'Cannot complete a job with status "{job.status}". Must be ON_THE_WAY or PICKED_UP.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    now = timezone.now()
    job.status = Job.Status.COMPLETED
    job.completed_at = now
    job.save(update_fields=['status', 'completed_at', 'updated_at'])
    job.request.status = 'COMPLETED'
    job.request.save(update_fields=['status', 'updated_at'])
    return Response(CollectorJobSerializer(job).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsCollector])
def collector_stats(request):
    profile, err = _get_profile(request.user)
    if err:
        return err

    jobs = Job.objects.filter(collector=request.user)
    total = jobs.count()
    completed = jobs.filter(status=Job.Status.COMPLETED).count()
    rejected = jobs.filter(status=Job.Status.REJECTED).count()
    missed = jobs.filter(status=Job.Status.MISSED).count()
    accepted_count = total - rejected
    acceptance_rate = round((accepted_count / total) * 100, 1) if total > 0 else 0.0
    completion_rate = round((completed / accepted_count) * 100, 1) if accepted_count > 0 else 0.0

    data = {
        'total_jobs': total,
        'completed_jobs': completed,
        'rejected_jobs': rejected,
        'missed_jobs': missed,
        'acceptance_rate': acceptance_rate,
        'completion_rate': completion_rate,
        'is_available': profile.is_available,
        'is_verified': profile.is_verified,
    }
    return Response(CollectorStatsSerializer(data).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsCollector])
def collector_notifications(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('job').order_by('-created_at')

    if request.query_params.get('unread', '').lower() == 'true':
        notifications = notifications.filter(is_read=False)

    return Response(NotificationSerializer(notifications, many=True).data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsCollector])
def mark_notification_read(request, pk):
    try:
        notification = Notification.objects.get(id=pk, user=request.user)
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)

    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)