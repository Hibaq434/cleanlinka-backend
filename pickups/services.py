from .models import Payment


def sync_pickup_charge_transaction(pickup, job=None):
    if not pickup.household_id:
        return None

    existing = getattr(pickup, "payment", None)
    if existing and existing.status == Payment.Status.PAID:
        return existing

    payment, _ = Payment.objects.update_or_create(
        request=pickup,
        defaults={
            "household": pickup.household,
            "amount": pickup.flat_rate_price,
            "status": Payment.Status.PENDING,
        },
    )
    return payment
