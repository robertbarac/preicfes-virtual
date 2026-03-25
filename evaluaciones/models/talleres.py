from django.db import models
from django.conf import settings
from curriculo.models import Modulo, Tema
from .banco import Pregunta, Opcion

class Taller(models.Model):
    ESTADOS = (
        ('borrador', 'Borrador'),
        ('publicado', 'Publicado'),
        ('oculto', 'Oculto'),
    )
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='talleres')
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True, related_name='talleres')
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='talleres_creados')
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    orden = models.PositiveIntegerField(default=0)
    intentos_permitidos = models.PositiveIntegerField(default=2)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.titulo

class PreguntaTaller(models.Model):
    taller = models.ForeignKey(Taller, on_delete=models.CASCADE, related_name='preguntas_taller')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

class IntentoTaller(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='intentos_taller')
    taller = models.ForeignKey(Taller, on_delete=models.CASCADE, related_name='intentos')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    puntaje_porcentaje = models.FloatField(blank=True, null=True, help_text="De 0 a 100")

    def __str__(self):
        return f"Intento Taller {self.id} - {self.usuario}"

class RespuestaTaller(models.Model):
    intento = models.ForeignKey(IntentoTaller, on_delete=models.CASCADE, related_name='respuestas')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL, null=True, blank=True)
    es_correcta = models.BooleanField(default=False)


# ─── Invalidación de caché ────────────────────────────────────────────────────
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.cache import cache
from curriculo.cache_keys import PROGRAMA_CACHE_KEY

@receiver(pre_save, sender=Taller)
def invalidar_cache_por_cambio_taller(sender, instance, **kwargs):
    """
    Borra el caché del programa cuando un Taller cambia de estado
    (ej: borrador → publicado, o publicado → oculto).
    """
    if instance.pk:
        try:
            anterior = Taller.objects.get(pk=instance.pk)
            if anterior.estado != instance.estado:
                cache.delete(PROGRAMA_CACHE_KEY)
        except Taller.DoesNotExist:
            pass
    else:
        # Taller nuevo: si nace publicado, invalida de una vez
        if instance.estado == 'publicado':
            cache.delete(PROGRAMA_CACHE_KEY)

