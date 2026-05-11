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

        if not User.objects.filter(phone_number=phone).exists():
            User.objects.create_superuser(
                phone_number=phone,
                name=name,
                password=password
            )
            self.stdout.write("Superuser created")
        else:
            self.stdout.write("Superuser already exists")