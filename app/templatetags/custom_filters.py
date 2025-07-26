from django import template

register = template.Library()

@register.filter
def patient_id_format(value):
    return f"P{value}"

@register.filter
def prescription_id_format(value):
    return f"Pres{value}"