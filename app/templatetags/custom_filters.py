from django import template

register = template.Library()

# --- ID format filters ---
@register.filter
def patient_id_format(value):
    """
    1 -> P0001 (optional)
    1 -> P1 (simple)
    নিচের যে কোনটা রাখতে পারেন
    """
    try:
        return f"P{int(value):04d}"  # nicer format
    except (TypeError, ValueError):
        return f"P{value}"

@register.filter
def prescription_id_format(value):
    try:
        return f"Pres{int(value):04d}"
    except (TypeError, ValueError):
        return f"Pres{value}"

# --- Duration filter ---
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

def to_bn_number(n):
    return str(n).translate(BN_DIGITS)

@register.filter
def duration_bn(days):
    try:
        d = int(days)
    except (TypeError, ValueError):
        return "-"

    if d == 0:
        return "চলবে"

    if d % 365 == 0:
        return f"{to_bn_number(d // 365)} বছর"
    if d % 30 == 0:
        return f"{to_bn_number(d // 30)} মাস"
    if d % 7 == 0:
        return f"{to_bn_number(d // 7)} সপ্তাহ"

    return f"{to_bn_number(d)} দিন"
