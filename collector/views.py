from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from pickups.models import Job, DisposalLog
from notifications.models import Notification
from .permissions import IsCollector
from .serializers import (
    CollectorProfileSerializer, CollectorJobSerializer,
    DisposalLogSerializer, CollectorStatsSerializer
)


@api_view(['GET', 'PATCH'])
@permission_classes([IsCollector])
def profile(request):
    collector_profile = request.user.collector_profile

    if request.method == 'GET':
        serializer = CollectorProfileSerializer(collector_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        data = request.data
        collector_profile.vehicle_type = data.get(
            'vehicle_type', collector_profile.vehicle_type
        )
        collector_profile.service_area = data.get(
            'service_area', collector_profile.service_area
        )
        collector_profile.is_available = data.get(
            'is_available', collector_profile.is_available
        )
        collector_profile.save()
        serializer = CollectorProfileSerializer(collector_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsCollector])
def job_list(request):
    jobs = Job.objects.filter(
        collector=request.user
    ).select_related('request').order_by('-created_at')
    serializer = CollectorJobSerializer(jobs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsCollector])
def pending_jobs(request):
    # Polling endpoint — frontend calls this every 10 seconds
    jobs = Job.objects.filter(
        collector=request.user,
        status='ASSIGNED'
    ).select_related('request').order_by('-created_at')
    serializer = CollectorJobSerializer(jobs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsCollector])
def accept_job(request, pk):
    try:
        job = Job.objects.get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if job.status != 'ASSIGNED':
        return Response(
            {'error': f'Cannot accept a job with status {job.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = 'ACCEPTED'
    job.accepted_at = timezone.now()
    job.save()

    return Response(
        {'message': 'Job accepted successfully.'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsCollector])
def decline_job(request, pk):
    try:
        job = Job.objects.get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if job.status != 'ASSIGNED':
        return Response(
            {'error': f'Cannot decline a job with status {job.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = 'REJECTED'
    job.save()

    # Mark pickup request back to pending for reassignment
    job.request.status = 'PENDING'
    job.request.save()

    return Response(
        {'message': 'Job declined. Admin will reassign.'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsCollector])
def start_job(request, pk):
    try:
        job = Job.objects.get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if job.status != 'ACCEPTED':
        return Response(
            {'error': f'Cannot start a job with status {job.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    job.status = 'ON_THE_WAY'
    job.save()

    return Response(
        {'message': 'Job started. On the way to household.'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsCollector])
def complete_job(request, pk):
    try:
        job = Job.objects.get(id=pk, collector=request.user)
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if job.status not in ['ON_THE_WAY', 'PICKED_UP']:
        return Response(
            {'error': f'Cannot complete a job with status {job.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Handle optional disposal log
    disposal_data = request.data.get('disposal_log')
    if disposal_data:
        serializer = DisposalLogSerializer(data=disposal_data)
        if serializer.is_valid():
            DisposalLog.objects.create(job=job, **serializer.validated_data)
        else:
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

    job.status = 'COMPLETED'
    job.completed_at = timezone.now()
    job.save()

    job.request.status = 'COMPLETED'
    job.request.save()

    return Response(
        {'message': 'Job completed successfully.'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsCollector])
def stats(request):
    jobs = Job.objects.filter(collector=request.user)
    total = jobs.count()
    completed = jobs.filter(status='COMPLETED').count()

    data = {
        'total_jobs': total,
        'completed_jobs': completed,
        'accepted_jobs': jobs.filter(status='ACCEPTED').count(),
        'rejected_jobs': jobs.filter(status='REJECTED').count(),
        'missed_jobs': jobs.filter(status='MISSED').count(),
        'completion_rate': round(
            (completed / total * 100) if total > 0 else 0, 2
        ),
    }
    serializer = CollectorStatsSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsCollector])
def notification_list(request):
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    data = [
        {
            'id': n.id,
            'channel': n.channel,
            'event': n.event,
            'message': n.message,
            'status': n.status,
            'created_at': n.created_at,
        }
        for n in notifications
    ]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsCollector])
def mark_notification_read(request, pk):
    try:
        notification = Notification.objects.get(
            id=pk, recipient=request.user
        )
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    notification.status = 'SENT'
    notification.save()

    return Response(
        {'message': 'Notification marked as read.'},
        status=status.HTTP_200_OK
    )