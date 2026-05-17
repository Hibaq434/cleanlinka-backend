import random
import string
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import OTPVerification


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp(user, channel='EMAIL'):
    print(f"[DEBUG] send_otp called with channel: {channel}")
    
    # Invalidate existing unused OTPs
    OTPVerification.objects.filter(
        user=user,
        is_used=False
    ).update(is_used=True)

    code = generate_otp()
    expires_at = timezone.now() + timedelta(minutes=10)

    otp = OTPVerification.objects.create(
        user=user,
        code=code,
        channel=channel,
        expires_at=expires_at
    )

    print(f"[DEBUG] channel is SMS: {channel == 'SMS'}")
    print(f"[DEBUG] user.phone_number: {user.phone_number}")

    if channel == 'EMAIL' and user.email:
        print(f"[DEBUG] Sending EMAIL to {user.email}")
        send_mail(
            subject='CleanLinka - Your Verification Code',
            message=f'Your verification code is: {code}\n\nThis code expires in 10 minutes.',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )

    if channel == 'SMS' and user.phone_number:
        print(f"[DEBUG] Sending SMS to {user.phone_number}")
        from notifications.sms import send_otp_sms
        result = send_otp_sms(user.phone_number, code)
        print(f"[SMS Response] {result}")

    print(f"[DEV] OTP for {user.phone_number}: {code}")

    return otp