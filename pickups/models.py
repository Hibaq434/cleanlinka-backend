from django.db import models
from users.models import User


class PickupRequest(models.Model):

    class Channel(models.TextChoices):
        APP = 'APP', 'App'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        CALL = 'CALL', 'Call'
        ADMIN_ENTRY = 'ADMIN_ENTRY', 'Admin Entry'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class WasteType(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        RECYCLABLE = 'RECYCLABLE', 'Recyclable'

    household = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='pickup_requests',
        null=True, blank=True
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    waste_type = models.CharField(
        max_length=20,
        choices=WasteType.choices,
        default=WasteType.GENERAL
    )
    lga = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=100, blank=True)
    preferred_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    flat_rate_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    logged_by_admin = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_logged_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request #{self.id} - {self.status} ({self.channel})"


class Job(models.Model):

    class Status(models.TextChoices):
        ASSIGNED = 'ASSIGNED', 'Assigned'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'
        ON_THE_WAY = 'ON_THE_WAY', 'On The Way'
        PICKED_UP = 'PICKED_UP', 'Picked Up'
        COMPLETED = 'COMPLETED', 'Completed'
        MISSED = 'MISSED', 'Missed'

    request = models.OneToOneField(
        PickupRequest, on_delete=models.CASCADE,
        related_name='job'
    )
    collector = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='jobs'
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='assigned_jobs'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED
    )
    household_confirmed = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job #{self.id} - {self.status}"


class DisposalLog(models.Model):

    class WasteCategory(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        PLASTIC = 'PLASTIC', 'Plastic'
        METAL = 'METAL', 'Metal'
        PAPER = 'PAPER', 'Paper'
        ORGANIC = 'ORGANIC', 'Organic'

    job = models.OneToOneField(
        Job, on_delete=models.CASCADE,
        related_name='disposal_log'
    )
    disposal_center = models.CharField(max_length=255)
    waste_category = models.CharField(
        max_length=20,
        choices=WasteCategory.choices
    )
    estimated_quantity_kg = models.DecimalField(
        max_digits=8, decimal_places=2
    )
    drop_off_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Disposal Log for Job #{self.job.id}"


class Rating(models.Model):
    job = models.OneToOneField(
        Job, on_delete=models.CASCADE,
        related_name='rating'
    )
    rated_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ratings_given'
    )
    collector = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ratings_received'
    )
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rating for Job #{self.job.id} - {self.score}/5"


class RequestEvent(models.Model):

    class EventType(models.TextChoices):
        CREATED = 'CREATED', 'Request Created'
        REVIEWED = 'REVIEWED', 'Request Reviewed'
        ASSIGNED = 'ASSIGNED', 'Collector Assigned'
        ACCEPTED = 'ACCEPTED', 'Collector Accepted'
        ON_THE_WAY = 'ON_THE_WAY', 'Collector En Route'
        COMPLETED = 'COMPLETED', 'Completed'
        PAYMENT_RECORDED = 'PAYMENT_RECORDED', 'Payment Recorded'
        FAILED = 'FAILED', 'Failed'

    request = models.ForeignKey(
        PickupRequest, on_delete=models.CASCADE,
        related_name='events'
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Event {self.event_type} for Request #{self.request.id}"


class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    class Method(models.TextChoices):
        CASH = 'CASH', 'Cash'
        TRANSFER = 'TRANSFER', 'Bank Transfer'
        CARD = 'CARD', 'Card'
        USSD = 'USSD', 'USSD'

    request = models.OneToOneField(
        PickupRequest, on_delete=models.CASCADE,
        related_name='payment'
    )
    household = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.status} - {self.amount}"