# cartera/context_processors.py

from django.db.models import Q
from academico.models import Alumno
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType


def alertas_cartera(request):
    """
    Context processor para exponer las alertas tempranas de cartera en todas las plantillas.
    - Superusers: ven el total global y muestra de alumnos activos sin deuda o sin cuotas.
    - Staff / Usuarios: ven sus propios alumnos registrados que aún no tienen cartera creada.
    """
    if not request.user or not request.user.is_authenticated:
        return {}

    user = request.user
    
    # Alumnos activos sin Deuda o con Deuda pero sin Cuotas generadas
    alumnos_sin_cartera_qs = Alumno.objects.filter(
        estado='activo'
    ).filter(
        Q(deuda__isnull=True) | Q(deuda__cuotas__isnull=True)
    ).distinct().select_related('grupo_actual', 'municipio')

    if user.is_superuser:
        total_sin_cartera = alumnos_sin_cartera_qs.count()
        muestra_sin_cartera = alumnos_sin_cartera_qs.order_by('-fecha_ingreso', '-id')[:5]
        return {
            'alumnos_sin_cartera_count': total_sin_cartera,
            'alumnos_sin_cartera_muestra': muestra_sin_cartera,
            'es_superuser_cartera': True,
        }
    elif user.is_staff:
        ct_alumno = ContentType.objects.get_for_model(Alumno)
        alumnos_creados_ids = LogEntry.objects.filter(
            user=user,
            content_type=ct_alumno,
            action_flag=ADDITION
        ).values_list('object_id', flat=True)

        mis_pendientes_qs = alumnos_sin_cartera_qs.filter(id__in=[int(i) for i in alumnos_creados_ids if i.isdigit()])
        total_mis_pendientes = mis_pendientes_qs.count()
        muestra_mis_pendientes = mis_pendientes_qs.order_by('-fecha_ingreso', '-id')[:5]

        return {
            'mis_alumnos_pendientes_count': total_mis_pendientes,
            'mis_alumnos_pendientes_muestra': muestra_mis_pendientes,
            'es_staff_cartera': True,
        }

    return {}
