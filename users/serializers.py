from rest_framework import serializers
from django.contrib.auth import get_user_model
from .location_scope import resolve_lga
from .models import AdminProfile, CollectorProfile, OTPVerification, NINVerification

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    national_id = serializers.CharField(required=False)
    vehicle_type = serializers.CharField(required=False)
    service_area = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    lga = serializers.CharField(required=False)
    area = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'role', 'password',
            'national_id', 'vehicle_type', 'service_area',
            'state', 'lga', 'area',
        ]

    def validate(self, data):
        role = data.get('role')
        if role == 'COLLECTOR':
            if not data.get('national_id'):
                raise serializers.ValidationError({'national_id': 'Required for collectors'})
            if not data.get('vehicle_type'):
                raise serializers.ValidationError({'vehicle_type': 'Required for collectors'})
            if not data.get('service_area'):
                raise serializers.ValidationError({'service_area': 'Required for collectors'})
            if not data.get('lga'):
                raise serializers.ValidationError({'lga': 'Required for collectors'})
        if role == 'ADMIN':
            if not data.get('state'):
                raise serializers.ValidationError({'state': 'Required for admins'})
            if not data.get('lga'):
                raise serializers.ValidationError({'lga': 'Required for admins'})
            normalized_lga = resolve_lga(
                lga=data.get('lga'),
                area=data.get('area'),
                service_area=data.get('service_area'),
            )
            if not normalized_lga:
                raise serializers.ValidationError({'lga': 'A valid local government is required for admins.'})
            if AdminProfile.objects.filter(
                lga__iexact=normalized_lga,
                user__role='ADMIN',
                user__is_active=True,
            ).exists():
                raise serializers.ValidationError({
                    'lga': 'An active admin already manages this local government.'
                })
        return data

    def create(self, validated_data):
        national_id = validated_data.pop('national_id', None)
        vehicle_type = validated_data.pop('vehicle_type', None)
        service_area = validated_data.pop('service_area', None)
        state = str(validated_data.pop('state', '') or '').strip()
        lga = resolve_lga(
            lga=validated_data.pop('lga', ''),
            area=validated_data.get('area', ''),
            service_area=service_area,
        )
        area = str(validated_data.pop('area', '') or '').strip()
        password = validated_data.pop('password')

        if not validated_data.get('email'):
            validated_data['email'] = None

        user = User(**validated_data)
        user.set_password(password)
        user.is_active = False
        if user.role == 'ADMIN':
            user.is_staff = True
        user.save()

        if user.role == 'COLLECTOR':
            CollectorProfile.objects.create(
                user=user,
                national_id=national_id,
                vehicle_type=vehicle_type,
                service_area=service_area,
                state=state,
                lga=lga,
                area=area or service_area or '',
            )
        if user.role == 'ADMIN':
            AdminProfile.objects.create(
                user=user,
                state=state,
                lga=lga,
                area=area,
            )
        return user


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField(max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    collector_profile = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    lga = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'role', 'is_active', 'is_verified',
            'created_at', 'collector_profile',
            'state', 'lga', 'area',
        ]

    def get_collector_profile(self, obj):
        if obj.role == 'COLLECTOR':
            try:
                profile = obj.collector_profile
                return {
                    'national_id': profile.national_id,
                    'vehicle_type': profile.vehicle_type,
                    'service_area': profile.service_area,
                    'state': profile.state,
                    'lga': profile.lga,
                    'area': profile.area,
                    'is_verified': profile.is_verified,
                    'is_available': profile.is_available,
                }
            except CollectorProfile.DoesNotExist:
                return None
        return None

    def _location_profile(self, obj):
        if obj.role == 'ADMIN':
            try:
                return obj.admin_profile
            except AdminProfile.DoesNotExist:
                return None
        if obj.role == 'COLLECTOR':
            try:
                return obj.collector_profile
            except CollectorProfile.DoesNotExist:
                return None
        return None

    def get_state(self, obj):
        profile = self._location_profile(obj)
        return getattr(profile, 'state', '') if profile else ''

    def get_lga(self, obj):
        profile = self._location_profile(obj)
        if not profile:
            return ''
        return resolve_lga(
            lga=getattr(profile, 'lga', ''),
            area=getattr(profile, 'area', ''),
            service_area=getattr(profile, 'service_area', ''),
        )

    def get_area(self, obj):
        profile = self._location_profile(obj)
        if not profile:
            return ''
        return getattr(profile, 'area', '') or getattr(profile, 'service_area', '')


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class NINVerificationSerializer(serializers.Serializer):
    nin = serializers.CharField(max_length=11, min_length=11)

    def validate_nin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('NIN must contain only numbers')
        return value


class NINVerificationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import NINVerification
        model = NINVerification
        fields = ['nin', 'status', 'created_at', 'reviewed_at']
