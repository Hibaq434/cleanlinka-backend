from rest_framework import serializers
from users.models import User, CollectorProfile
from pickups.models import Job, PickupRequest, DisposalLog
from locations.models import Location


class CollectorProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = CollectorProfile
        fields = [
            'name', 'phone_number', 'email',
            'national_id', 'vehicle_type', 'service_area',
            'is_verified', 'is_available'
        ]


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            'latitude', 'longitude',
            'address_text', 'landmark',
            'whatsapp_pin_url'
        ]


class PickupRequestSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    household_name = serializers.SerializerMethodField()
    household_phone = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'channel', 'waste_type', 'preferred_time',
            'notes', 'status',
            'bag_count', 'bag_size', 'collector_payout',
            'household_name', 'household_phone',
            'location', 'created_at'
        ]

    def get_location(self, obj):
        try:
            return LocationSerializer(obj.location).data
        except Exception:
            return None

    def get_household_name(self, obj):
        if obj.household:
            return obj.household.name
        return None

    def get_household_phone(self, obj):
        if obj.household:
            return obj.household.phone_number
        return None


class CollectorJobSerializer(serializers.ModelSerializer):
    request = PickupRequestSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'request', 'status',
            'household_confirmed', 'accepted_at',
            'completed_at', 'created_at'
        ]


class DisposalLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisposalLog
        fields = [
            'disposal_center', 'waste_category',
            'estimated_quantity_kg', 'drop_off_time'
        ]


class CollectorStatsSerializer(serializers.Serializer):
    total_jobs = serializers.IntegerField()
    completed_jobs = serializers.IntegerField()
    accepted_jobs = serializers.IntegerField()
    rejected_jobs = serializers.IntegerField()
    missed_jobs = serializers.IntegerField()
    completion_rate = serializers.FloatField()
