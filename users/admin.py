from django.contrib import admin
from .models import User, CollectorProfile, OTPVerification

admin.site.register(User)
admin.site.register(CollectorProfile)
admin.site.register(OTPVerification)