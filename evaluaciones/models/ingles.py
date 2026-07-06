from django.db import models
from django.conf import settings
from curriculo.models import Modulo

class ActividadVirtual(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='actividades')
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Actividad Virtual'
        verbose_name_plural = 'Actividades Virtuales'
        ordering = ['orden']

    def __str__(self):
        return self.titulo


class BloqueActividad(models.Model):
    TIPOS = (
        ('drag_drop',     'Drag & Drop (palabras a huecos)'),
        ('fill_dropdown', 'Rellenar con desplegable'),
        ('fill_type',     'Completar escribiendo'),
        ('audio_task',    'Tarea de Audio'),
    )
    actividad = models.ForeignKey(ActividadVirtual, on_delete=models.CASCADE, related_name='bloques')
    tipo      = models.CharField(max_length=20, choices=TIPOS)
    consigna  = models.TextField(help_text="Instrucciones para este bloque de ejercicios")
    contenido = models.TextField(help_text="Texto con corchetes [palabra] o [opcion1|opcion2]")
    distractores = models.CharField(max_length=255, blank=True, help_text="Opciones falsas separadas por comas (solo Drag & Drop)")
    orden     = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Bloque de Actividad'
        verbose_name_plural = 'Bloques de Actividad'
        ordering = ['orden']

    def __str__(self):
        return f"{self.actividad.titulo} - Bloque {self.orden} ({self.get_tipo_display()})"


class IntentoActividad(models.Model):
    actividad = models.ForeignKey(ActividadVirtual, on_delete=models.CASCADE, related_name='intentos')
    usuario   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='intentos_actividad')
    respuestas = models.JSONField(help_text="Respuestas de texto estructuradas: {bloque_id: {gap_idx: valor}}")
    retroalimentacion = models.JSONField(null=True, blank=True, help_text="Retroalimentación automática por bloque")
    puntaje   = models.FloatField(null=True, blank=True, help_text="Nota del intento de 0 a 100")
    fecha     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Intento de Actividad'
        verbose_name_plural = 'Intentos de Actividad'

    def __str__(self):
        return f"Intento {self.usuario.username} - {self.actividad.titulo}"


class IntentoAudioBloque(models.Model):
    intento   = models.ForeignKey(IntentoActividad, on_delete=models.CASCADE, related_name='audios_intento', null=True, blank=True)
    bloque    = models.ForeignKey(BloqueActividad, on_delete=models.CASCADE, related_name='audios')
    usuario   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audios_bloque')
    audio     = models.FileField(upload_to='ingles/audios/%Y/%m/')
    fecha     = models.DateTimeField(auto_now_add=True)
    revisado  = models.BooleanField(default=False)
    comentario_profe = models.TextField(blank=True)
    calificacion     = models.FloatField(null=True, blank=True, help_text="Calificación del audio de 0 a 100")

    class Meta:
        verbose_name = 'Entrega de Audio de Bloque'
        verbose_name_plural = 'Entregas de Audio de Bloque'

    def __str__(self):
        return f"Audio de {self.usuario.username} en Bloque {self.bloque.id}"
