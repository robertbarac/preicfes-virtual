from .models import ConfiguracionPlataforma

def configuracion_global(request):
    try:
        config = ConfiguracionPlataforma.objects.first()
        tema = config.tema_menu if config else 'teal'
    except Exception:
        # En caso de que la tabla aún no exista
        tema = 'teal'
    
    return {'TEMA_MENU': tema}
