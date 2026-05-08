from django.db import models
from users.models import User


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        JOB_ASSIGNED = 'JOB_ASSIGNED', 'Job Assigned'
        JOB_CANCELLED = 'JOB_CANCELLED', 'Job Cancelled'
        GENERAL = 'GENERAL', 'General'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL
    )
    title = models.CharField(max_length=255)
    message = models.TextField()

    # String reference avoids circular import: notifications -> pickups -> notifications
    job = models.ForeignKey(
        'pickups.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification → {self.user.name}: {self.title}"