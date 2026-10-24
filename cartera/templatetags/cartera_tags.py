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
    """Convierte la clave o id del concepto a su nombre para mostrar"""
    if hasattr(concepto_key, 'nombre'):
        return concepto_key.nombre
    try:
        from cartera.models import ConceptoEgreso
        conc = ConceptoEgreso.objects.filter(id=int(concepto_key)).first()
        if conc:
            return conc.nombre
    except (ValueError, TypeError, Exception):
        pass
    try:
        return dict(Egreso.CONCEPTO_CHOICES).get(concepto_key, str(concepto_key))
    except (KeyError, AttributeError):
        return str(concepto_key)

@register.filter(name='divide')
def divide(value, arg):
    """Divide el valor por el argumento"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0