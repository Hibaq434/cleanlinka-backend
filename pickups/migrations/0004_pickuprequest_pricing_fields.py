from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models


MONEY_QUANT = Decimal("1")
VAT_RATE = Decimal("0.075")
COLLECTOR_RATE = Decimal("0.70")
MINIMUM_PICKUP = Decimal("1500.00")


def money(value):
    return Decimal(value or 0).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def backfill_pricing(apps, schema_editor):
    PickupRequest = apps.get_model("pickups", "PickupRequest")

    for pickup in PickupRequest.objects.all():
        total_amount = money(pickup.flat_rate_price)
        if total_amount <= 0:
            service_amount = MINIMUM_PICKUP
            vat_amount = money(service_amount * VAT_RATE)
            total_amount = money(service_amount + vat_amount)
            pickup.flat_rate_price = total_amount
        else:
            service_amount = money(total_amount / (Decimal("1") + VAT_RATE))
            vat_amount = money(total_amount - service_amount)

        collector_payout = money(service_amount * COLLECTOR_RATE)
        company_service_share = money(service_amount - collector_payout)

        pickup.bag_count = pickup.bag_count or 1
        pickup.bag_size = pickup.bag_size or "standard"
        pickup.bag_unit_price = pickup.bag_unit_price or Decimal("1000.00")
        pickup.service_amount = service_amount
        pickup.vat_rate = VAT_RATE
        pickup.vat_amount = vat_amount
        pickup.total_amount = total_amount
        pickup.collector_payout = collector_payout
        pickup.company_service_share = company_service_share
        pickup.company_revenue = money(company_service_share + vat_amount)
        pickup.save(update_fields=[
            "flat_rate_price",
            "bag_count",
            "bag_size",
            "bag_unit_price",
            "service_amount",
            "vat_rate",
            "vat_amount",
            "total_amount",
            "collector_payout",
            "company_service_share",
            "company_revenue",
        ])


class Migration(migrations.Migration):

    dependencies = [
        ("pickups", "0003_payment"),
    ]

    operations = [
        migrations.AddField(
            model_name="pickuprequest",
            name="bag_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="bag_size",
            field=models.CharField(default="standard", max_length=20),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="bag_unit_price",
            field=models.DecimalField(decimal_places=2, default=1000.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="service_amount",
            field=models.DecimalField(decimal_places=2, default=1500.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="vat_rate",
            field=models.DecimalField(decimal_places=4, default=0.075, max_digits=5),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="vat_amount",
            field=models.DecimalField(decimal_places=2, default=113.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="total_amount",
            field=models.DecimalField(decimal_places=2, default=1613.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="collector_payout",
            field=models.DecimalField(decimal_places=2, default=1050.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="company_service_share",
            field=models.DecimalField(decimal_places=2, default=450.00, max_digits=10),
        ),
        migrations.AddField(
            model_name="pickuprequest",
            name="company_revenue",
            field=models.DecimalField(decimal_places=2, default=563.00, max_digits=10),
        ),
        migrations.RunPython(backfill_pricing, migrations.RunPython.noop),
    ]
