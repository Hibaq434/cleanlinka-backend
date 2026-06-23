from decimal import Decimal, ROUND_HALF_UP


MINIMUM_PICKUP = Decimal("1500.00")
VAT_RATE = Decimal("0.075")
COLLECTOR_RATE = Decimal("0.70")
MONEY_QUANT = Decimal("1")

BAG_SIZES = {
    "small": {"label": "Small", "price": Decimal("700.00")},
    "standard": {"label": "Standard", "price": Decimal("1000.00")},
    "large": {"label": "Large", "price": Decimal("1500.00")},
}


def money(value):
    return Decimal(value or 0).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def normalize_bag_size(value):
    key = str(value or "").strip().lower()
    return key if key in BAG_SIZES else "standard"


def normalize_bag_count(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def calculate_bag_pricing(bag_count=1, bag_size="standard"):
    size_key = normalize_bag_size(bag_size)
    count = normalize_bag_count(bag_count)
    unit_price = BAG_SIZES[size_key]["price"]
    raw_bag_amount = money(unit_price * count)
    service_amount = max(raw_bag_amount, MINIMUM_PICKUP)
    vat_amount = money(service_amount * VAT_RATE)
    total_amount = money(service_amount + vat_amount)
    collector_payout = money(service_amount * COLLECTOR_RATE)
    company_service_share = money(service_amount - collector_payout)
    company_revenue = money(company_service_share + vat_amount)

    return {
        "bag_count": count,
        "bag_size": size_key,
        "bag_unit_price": money(unit_price),
        "raw_bag_amount": raw_bag_amount,
        "service_amount": money(service_amount),
        "vat_rate": VAT_RATE,
        "vat_amount": vat_amount,
        "total_amount": total_amount,
        "collector_payout": collector_payout,
        "company_service_share": company_service_share,
        "company_revenue": company_revenue,
    }


def apply_pricing_fields(data, bag_count=None, bag_size=None):
    pricing = calculate_bag_pricing(
        bag_count if bag_count is not None else data.get("bag_count", 1),
        bag_size if bag_size is not None else data.get("bag_size", "standard"),
    )
    model_pricing = {key: value for key, value in pricing.items() if key != "raw_bag_amount"}
    data.update(model_pricing)
    data["flat_rate_price"] = pricing["total_amount"]
    return data
