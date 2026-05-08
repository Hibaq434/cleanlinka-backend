from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CollectorProfile, OTPVerification, NINVerification

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    national_id = serializers.CharField(required=False)
    vehicle_type = serializers.CharField(required=False)
    service_area = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'role', 'password',
            'national_id', 'vehicle_type', 'service_area'
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
        return data

    def create(self, validated_data):
        national_id = validated_data.pop('national_id', None)
        vehicle_type = validated_data.pop('vehicle_type', None)
        service_area = validated_data.pop('service_area', None)

        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = False
        user.save()

        if user.role == 'COLLECTOR':
            CollectorProfile.objects.create(
                user=user,
                national_id=national_id,
                vehicle_type=vehicle_type,
                service_area=service_area,
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

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'role', 'is_active', 'is_verified',
            'created_at', 'collector_profile'
        ]

    def get_collector_profile(self, obj):
        if obj.role == 'COLLECTOR':
            try:
                profile = obj.collector_profile
                return {
                    'national_id': profile.national_id,
                    'vehicle_type': profile.vehicle_type,
                    'service_area': profile.service_area,
                    'is_verified': profile.is_verified,
                    'is_available': profile.is_available,
                }
            except CollectorProfile.DoesNotExist:
                return None
        return None


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