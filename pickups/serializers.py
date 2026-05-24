from rest_framework import serializers
from .models import PickupRequest
from locations.models import Location


class CreatePickupRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=['APP', 'WHATSAPP', 'CALL', 'ADMIN_ENTRY'])
    waste_type = serializers.ChoiceField(choices=['GENERAL', 'RECYCLABLE'], default='GENERAL')
    preferred_time = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    flat_rate_price = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    address_text = serializers.CharField()
    landmark = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=False, allow_null=True
    )
    whatsapp_pin_url = serializers.URLField(required=False, allow_blank=True)

    def create(self, validated_data):
        address_text = validated_data.pop('address_text')
        landmark = validated_data.pop('landmark', '')
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        whatsapp_pin_url = validated_data.pop('whatsapp_pin_url', '')

        pickup = PickupRequest.objects.create(**validated_data)

        Location.objects.create(
            request=pickup,
            address_text=address_text,
            landmark=landmark,
            latitude=latitude,
            longitude=longitude,
            whatsapp_pin_url=whatsapp_pin_url
        )

        return pickup


class PickupRequestDetailSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    job_status = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'channel', 'waste_type', 'preferred_time',
            'notes', 'flat_rate_price', 'status',
            'location', 'job_status', 'created_at'
        ]

    def get_location(self, obj):
        try:
            loc = obj.location
            return {
                'address_text': loc.address_text,
                'landmark': loc.landmark,
                'latitude': str(loc.latitude) if loc.latitude else None,
                'longitude': str(loc.longitude) if loc.longitude else None,
                'whatsapp_pin_url': loc.whatsapp_pin_url,
            }
        except Exception:
            return None

    def get_job_status(self, obj):
        try:
            return obj.job.status
        except Exception:
            return None