from django.db import models
from pickups.models import PickupRequest


class Location(models.Model):
    request = models.OneToOneField(
        PickupRequest, on_delete=models.CASCADE,
        related_name='location'
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    address_text = models.TextField()
    landmark = models.CharField(max_length=255, blank=True)
    whatsapp_pin_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Location for Request #{self.request.id}"