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
