# cartera/utils_audit.py

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType


def registrar_log_audit(user, obj, accion=ADDITION, mensaje=""):
    """
    Registra una acción en LogEntry de Django Admin para auditoría oficial.
    accion: ADDITION (1), CHANGE (2), DELETION (3)
    """
    if not user or not user.is_authenticated:
        return None
    try:
        return LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=str(obj.pk),
            object_repr=str(obj)[:200],
            action_flag=accion,
            change_message=mensaje or ("Creado desde la web" if accion == ADDITION else "Modificado desde la web")
        )
    except Exception as e:
        print(f"Error en auditoría LogEntry: {e}")
        return None
