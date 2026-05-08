from rest_framework import serializers
from users.models import CollectorProfile
from pickups.models import Job, PickupRequest
from notifications.models import Notification


class CollectorProfileSerializer(serializers.ModelSerializer):
    # Flatten user fields onto the profile response
    name = serializers.CharField(source='user.name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    is_verified_account = serializers.BooleanField(source='user.is_verified', read_only=True)

    class Meta:
        model = CollectorProfile
        fields = [
            'name', 'phone_number', 'email',
            'is_active', 'is_verified_account',
            'national_id', 'vehicle_type', 'service_area',
            'is_verified', 'is_available', 'created_at',
        ]
        read_only_fields = [
            # These are set by admin only — collectors cannot self-edit them
            'national_id', 'is_verified', 'service_area',
            'created_at', 'name', 'phone_number', 'email',
            'is_active', 'is_verified_account',
        ]


class PickupRequestSummarySerializer(serializers.ModelSerializer):
    """Lightweight nested view of a pickup request shown inside a job card."""
    household_name = serializers.SerializerMethodField()
    household_phone = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'channel', 'waste_type', 'preferred_time',
            'notes', 'flat_rate_price', 'status',
            'household_name', 'household_phone',
        ]

    def get_household_name(self, obj):
        return obj.household.name if obj.household else None

    def get_household_phone(self, obj):
        return obj.household.phone_number if obj.household else None


class CollectorJobSerializer(serializers.ModelSerializer):
    """Used for all job list and job action responses."""
    request_details = PickupRequestSummarySerializer(source='request', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'status', 'household_confirmed',
            'accepted_at', 'completed_at', 'created_at',
            'request_details',
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title',
            'message', 'job', 'is_read', 'created_at',
        ]
        read_only_fields = [
            'id', 'notification_type', 'title',
            'message', 'job', 'created_at',
        ]


class CollectorStatsSerializer(serializers.Serializer):
    total_jobs = serializers.IntegerField()
    completed_jobs = serializers.IntegerField()
    rejected_jobs = serializers.IntegerField()
    missed_jobs = serializers.IntegerField()
    acceptance_rate = serializers.FloatField()
    completion_rate = serializers.FloatField()
    is_available = serializers.BooleanField()
    is_verified = serializers.BooleanField()