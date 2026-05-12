from django.db import models
from users.models import User


class Notification(models.Model):

    class Channel(models.TextChoices):
        SMS = 'SMS', 'SMS'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        PUSH = 'PUSH', 'Push'

    class Event(models.TextChoices):
        REQUEST_RECEIVED = 'REQUEST_RECEIVED', 'Request Received'
        JOB_ASSIGNED = 'JOB_ASSIGNED', 'Job Assigned'
        COLLECTOR_ACCEPTED = 'COLLECTOR_ACCEPTED', 'Collector Accepted'
        COLLECTOR_ON_THE_WAY = 'COLLECTOR_ON_THE_WAY', 'Collector On The Way'
        JOB_COMPLETED = 'JOB_COMPLETED', 'Job Completed'
        JOB_MISSED = 'JOB_MISSED', 'Job Missed'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='notifications'
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    event = models.CharField(max_length=30, choices=Event.choices)
    message = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.name} - {self.event}"