def calculate_rate(price, area):
    """Return property price per square foot with basic input validation."""
    try:
        price_value = float(price)
        area_value = float(area)
    except (TypeError, ValueError) as exc:
        raise ValueError("Price and area must be numeric values.") from exc
    if price_value <= 0:
        raise ValueError("Price must be greater than 0.")
    if area_value <= 0:
        raise ValueError("Area must be greater than 0.")
    return price_value / area_value
