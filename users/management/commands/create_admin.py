from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()

        phone = config("DJANGO_SUPERUSER_PHONE_NUMBER", default=None)
        name = config("DJANGO_SUPERUSER_NAME", default="Admin")
        password = config("DJANGO_SUPERUSER_PASSWORD", default=None)

        if not phone or not password:
            self.stdout.write("Missing env variables")
            return

        user = User.objects.filter(phone_number=phone).first()
        if not user:
            User.objects.create_superuser(
                phone_number=phone,
                name=name,
                password=password
            )
            self.stdout.write("Superuser created")
            return

        # Ensure existing admin is usable (common when `is_active` defaults to False)
        changed = False

        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if hasattr(user, 'is_verified') and not user.is_verified:
            user.is_verified = True
            changed = True

        # Keep password in sync with env var
        if password:
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            self.stdout.write("Superuser updated")
        else:
            self.stdout.write("Superuser already exists")
