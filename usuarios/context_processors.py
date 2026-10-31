from .models import ConfiguracionPlataforma

from django.core.cache import cache

def configuracion_global(request):
    tema = cache.get('tema_menu_global')
    if tema is None:
        try:
            config = ConfiguracionPlataforma.objects.first()
            tema = config.tema_menu if config else 'campus'
        except Exception:
            tema = 'campus'
        cache.set('tema_menu_global', tema, 3600)  # Cachear 1 hora
    return {'TEMA_MENU': tema}


def mis_programas(request):
    """
    Expone globalmente en las plantillas los programas a los que el usuario
    está asignado según su rol (estudiante o profesor).
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
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

    # Si es profesor (pertenece al grupo Profesor/Teacher)
    if user.es_docente:
        mis_progs = list(user.programas_docente.filter(activo=True))
        es_profesor_ingles = user.programas_docente.filter(tipo='ingles', activo=True).exists()
        return {
            'mis_programas': mis_progs,
            'soy_teacher_de': mis_progs,
            'soy_student_de': [],
            'es_profesor_ingles': es_profesor_ingles,
        }
        
    # Si es estudiante (Student o VirtualStudent)
    tiene_acceso = user.tiene_acceso_programa_activo() if hasattr(user, 'tiene_acceso_programa_activo') else False
    prog_efectivo = user.obtener_programa_efectivo() if hasattr(user, 'obtener_programa_efectivo') else user.programa

    if tiene_acceso and prog_efectivo and prog_efectivo.activo:
        return {
            'mis_programas': [prog_efectivo],
            'soy_teacher_de': [],
            'soy_student_de': [prog_efectivo],
            'es_profesor_ingles': False,
        }
            
    return {
        'mis_programas': [],
        'soy_teacher_de': [],
        'soy_student_de': [],
        'es_profesor_ingles': False,
    }

