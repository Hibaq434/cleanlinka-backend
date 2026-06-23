from rest_framework import serializers
from users.models import User, CollectorProfile, NINVerification
from pickups.models import PickupRequest, Job, DisposalLog
from pickups.pricing import BAG_SIZES, apply_pricing_fields


PRICING_FIELDS = [
    'bag_count', 'bag_size', 'bag_unit_price',
    'service_amount', 'vat_rate', 'vat_amount',
    'total_amount', 'collector_payout',
    'company_service_share', 'company_revenue',
]


class CollectorListSerializer(serializers.ModelSerializer):
    collector_profile = serializers.SerializerMethodField()
    nin_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'is_active', 'is_verified', 'created_at',
            'collector_profile', 'nin_status'
        ]

    def get_collector_profile(self, obj):
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

    def get_nin_status(self, obj):
        try:
            return obj.nin_verification.status
        except NINVerification.DoesNotExist:
            return None


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number',
            'email', 'role', 'is_active',
            'is_verified', 'created_at'
        ]


class PickupRequestSerializer(serializers.ModelSerializer):
    household_name = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'household', 'household_name', 'channel',
            'waste_type', 'preferred_time', 'notes',
            'flat_rate_price', *PRICING_FIELDS,
            'status', 'created_at'
        ]

    def get_household_name(self, obj):
        if obj.household:
            return obj.household.name
        return None


class JobSerializer(serializers.ModelSerializer):
    collector_name = serializers.SerializerMethodField()
    request_details = PickupRequestSerializer(source='request', read_only=True)

    # FIX: Make raw FK fields write-only so internal IDs are not
    # exposed in GET responses. The frontend gets collector_name and
    # request_details (nested) for reading; it sends collector/request
    # IDs only when creating or patching.
    collector = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='COLLECTOR'),
        write_only=True,
        required=False
    )
    request = serializers.PrimaryKeyRelatedField(
        queryset=PickupRequest.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Job
        fields = [
            'id', 'request', 'request_details', 'collector',
            'collector_name', 'assigned_by', 'status',
            'household_confirmed', 'accepted_at',
            'completed_at', 'created_at'
        ]
        # assigned_by is set server-side, never from client input
        read_only_fields = ['assigned_by', 'accepted_at', 'completed_at', 'created_at']

    def get_collector_name(self, obj):
        if obj.collector:
            return obj.collector.name
        return None


class AssignJobSerializer(serializers.Serializer):
    collector_id = serializers.IntegerField()

    def validate_collector_id(self, value):
        # FIX: Guard both User.DoesNotExist and CollectorProfile.DoesNotExist
        try:
            user = User.objects.get(id=value, role='COLLECTOR')
        except User.DoesNotExist:
            raise serializers.ValidationError('Collector not found')

        try:
            profile = user.collector_profile
        except CollectorProfile.DoesNotExist:
            raise serializers.ValidationError(
                'Collector has no profile and cannot be assigned jobs'
            )

        if not profile.is_verified:
            raise serializers.ValidationError('Collector is not verified')

        return value


class CreatePickupRequestSerializer(serializers.ModelSerializer):
    bag_count = serializers.IntegerField(required=False, min_value=1, default=1)
    bag_size = serializers.ChoiceField(choices=list(BAG_SIZES.keys()), required=False, default='standard')

    class Meta:
        model = PickupRequest
        fields = [
            'household', 'channel', 'waste_type',
            'preferred_time', 'notes', 'flat_rate_price',
            'bag_count', 'bag_size'
        ]

    def create(self, validated_data):
        # FIX: Handle logged_by_admin passed from the view via save().
        # DRF forwards extra kwargs from save() into create() as part of
        # validated_data — we pop it here before creating the instance.
        # If your PickupRequest model has a logged_by_admin FK field,
        # keep the line below. If not, remove it and log separately.
        logged_by_admin = validated_data.pop('logged_by_admin', None)
        apply_pricing_fields(validated_data)
        pickup = PickupRequest.objects.create(**validated_data)

        if logged_by_admin:
            # If your model tracks this, set it here.
            # Example: pickup.logged_by_admin = logged_by_admin
            # pickup.save(update_fields=['logged_by_admin'])
            #
            # If you don't have this field yet, this is where you'd add it.
            # For now it's a no-op so nothing breaks.
            pass

        return pickup


class DashboardSerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    completed_requests = serializers.IntegerField()
    failed_requests = serializers.IntegerField()
    total_collectors = serializers.IntegerField()
    verified_collectors = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    total_households = serializers.IntegerField()
