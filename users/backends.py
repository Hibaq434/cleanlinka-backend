from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class PhoneBackend(BaseBackend):
    def authenticate(self, request, username=None, phone_number=None, password=None, **kwargs):
        # Support Django's conventional `username` kwarg while using `phone_number`
        # as the actual identifier.
        identifier = phone_number or username or kwargs.get('phone_number') or kwargs.get(User.USERNAME_FIELD)
        if not identifier or password is None:
            return None

        try:
            user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            return None

        if not getattr(user, 'is_active', True):
            return None

        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None