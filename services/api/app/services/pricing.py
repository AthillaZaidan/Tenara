from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import AppValidationError
from app.models import FabricListing


def validate_quantity(listing: FabricListing, qty: Decimal) -> None:
    if qty < listing.min_quantity:
        raise AppValidationError(f"Minimum purchase is {listing.min_quantity}", field="quantity")
    if (qty - listing.min_quantity) % listing.quantity_increment != 0:
        raise AppValidationError(
            f"Quantity must follow the increment of {listing.quantity_increment}", field="quantity"
        )
    if listing.selling_unit == "piece" and qty != qty.to_integral_value():
        raise AppValidationError("Piece listings are sold in whole pieces", field="quantity")


def line_subtotal(price_idr: int, qty: Decimal) -> int:
    """Integer IDR, rounded half up."""
    return int((Decimal(price_idr) * qty).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def commission(gross_idr: int, bps: int) -> int:
    """Integer IDR commission, rounded half up; symmetric for negative (adjustment) amounts."""
    sign = -1 if gross_idr < 0 else 1
    return sign * ((abs(gross_idr) * bps + 5000) // 10000)
