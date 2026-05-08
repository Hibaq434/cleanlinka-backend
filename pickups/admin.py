from django.contrib import admin
from .models import PickupRequest, Job, DisposalLog, Rating

admin.site.register(PickupRequest)
admin.site.register(Job)
admin.site.register(DisposalLog)
admin.site.register(Rating)
