from .models import ConfiguracionPlataforma

from django.core.cache import cache

def configuracion_global(request):
    tema = cache.get('tema_menu_global')
    if tema is None:
        try:
            config = ConfiguracionPlataforma.objects.first()
            tema = config.tema_menu if config else 'teal'
        except Exception:
            tema = 'teal'
        cache.set('tema_menu_global', tema, 3600)  # Cachear 1 hora
    return {'TEMA_MENU': tema}


def mis_programas(request):
    """
    Expone globalmente en las plantillas los programas a los que el usuario
    está asignado según su rol (estudiante o profesor).
    """
    if not request.user or not request.user.is_authenticated:
        return {}
    
    user = request.user
    from curriculo.models import Programa

    # Si es superusuario, tiene acceso a todos los programas activos
    if user.is_superuser:
        mis_progs = list(Programa.objects.filter(activo=True))
        return {
            'mis_programas': mis_progs,
            'soy_teacher_de': mis_progs,
            'soy_student_de': [],
            'es_profesor_ingles': True,
        }

    # Si es profesor (role == 'teacher')
    if user.role == 'teacher':
        mis_progs = list(user.programas_docente.filter(activo=True))
        es_profesor_ingles = user.programas_docente.filter(tipo='ingles', activo=True).exists()
        return {
            'mis_programas': mis_progs,
            'soy_teacher_de': mis_progs,
            'soy_student_de': [],
            'es_profesor_ingles': es_profesor_ingles,
        }
        
    # Si es estudiante (role in ['student', 'virtual_student'])
    # Verificar si tiene una suscripción activa
    from suscripciones.models import Subscription
    from django.utils import timezone
    hoy = timezone.now().date()
    suscripcion_activa = user.subscriptions.filter(active=True, end_date__gte=hoy).exists()
    
    if suscripcion_activa and user.programa_id:
        if user.programa.activo:
            return {
                'mis_programas': [user.programa],
                'soy_teacher_de': [],
                'soy_student_de': [user.programa],
                'es_profesor_ingles': False,
            }
            
    return {
        'mis_programas': [],
        'soy_teacher_de': [],
        'soy_student_de': [],
        'es_profesor_ingles': False,
    }

