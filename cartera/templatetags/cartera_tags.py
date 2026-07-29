from django import template
from calendar import month_name
from cartera.models import Egreso

register = template.Library()

@register.filter(name='subtract')
def subtract(value, arg):
    """Resta el argumento del valor"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def absolute(value):
    return abs(value)

@register.filter(name='get_month_name')
def get_month_name(month_number):
    """Convierte número de mes a nombre (1 -> 'Enero')"""
    try:
        return month_name[month_number]
    except (IndexError, KeyError):
        return str(month_number)

@register.filter(name='get_concepto_display')
def get_concepto_display(concepto_key):
    """Convierte la clave del concepto a su nombre para mostrar"""
    try:
        return dict(Egreso.CONCEPTO_CHOICES).get(concepto_key, concepto_key)
    except (KeyError, AttributeError):
        return concepto_key

@register.filter(name='divide')
def divide(value, arg):
    """Divide el valor por el argumento"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0