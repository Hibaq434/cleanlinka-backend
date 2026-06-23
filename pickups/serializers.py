from rest_framework import serializers
from .models import PickupRequest, RequestEvent
from .pricing import BAG_SIZES, apply_pricing_fields
from locations.models import Location


PRICING_FIELDS = [
    'bag_count', 'bag_size', 'bag_unit_price',
    'service_amount', 'vat_rate', 'vat_amount',
    'total_amount', 'collector_payout',
    'company_service_share', 'company_revenue',
]


def parse_request_notes(value=''):
    parsed = {'address': '', 'lga': '', 'area': '', 'notes': ''}
    extras = []

    for raw_line in str(value or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('Address:'):
            parsed['address'] = line.replace('Address:', '', 1).strip()
        elif line.startswith('LGA:'):
            parsed['lga'] = line.replace('LGA:', '', 1).strip()
        elif line.startswith('Area:'):
            parsed['area'] = line.replace('Area:', '', 1).strip()
        elif line.startswith('Notes:'):
            extras.append(line.replace('Notes:', '', 1).strip())
        else:
            extras.append(line)

    parsed['notes'] = '\n'.join(extras).strip()
    return parsed


class CreatePickupRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=['APP', 'WHATSAPP', 'CALL', 'ADMIN_ENTRY'])
    waste_type = serializers.ChoiceField(choices=['GENERAL', 'RECYCLABLE'], default='GENERAL')
    lga = serializers.CharField(required=False, allow_blank=True)
    area = serializers.CharField(required=False, allow_blank=True)
    preferred_time = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    flat_rate_price = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bag_count = serializers.IntegerField(required=False, min_value=1, default=1)
    bag_size = serializers.ChoiceField(choices=list(BAG_SIZES.keys()), required=False, default='standard')
    address_text = serializers.CharField(required=False, allow_blank=True)
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
        pricing = apply_pricing_fields(
            validated_data,
            bag_count=validated_data.get('bag_count'),
            bag_size=validated_data.get('bag_size'),
        )
        address_text = validated_data.pop('address_text', '')
        if not address_text:
            parsed_notes = parse_request_notes(validated_data.get('notes', ''))
            address_text = parsed_notes.get('address', '')
        landmark = validated_data.pop('landmark', '')
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        whatsapp_pin_url = validated_data.pop('whatsapp_pin_url', '')
        validated_data.update(pricing)

        pickup = PickupRequest.objects.create(**validated_data)

        Location.objects.create(
            request=pickup,
            address_text=address_text,
            landmark=landmark,
            latitude=latitude,
            longitude=longitude,
            whatsapp_pin_url=whatsapp_pin_url
        )

        RequestEvent.objects.create(
            request=pickup,
            event_type='CREATED',
            description='Pickup request created'
        )

        return pickup


class PickupRequestDetailSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    job_status = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'channel', 'waste_type', 'lga', 'area',
            'preferred_time', 'notes', 'flat_rate_price', 'status',
            *PRICING_FIELDS,
            'address', 'location', 'job_status', 'created_at'
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

    def get_address(self, obj):
        try:
            return obj.location.address_text
        except Exception:
            return None

    def get_job_status(self, obj):
        try:
            return obj.job.status
        except Exception:
            return None


class RequestEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestEvent
        fields = ['id', 'event_type', 'description', 'created_at']


class HouseholdPickupRequestSerializer(PickupRequestDetailSerializer):
    pass
