from django.db import models
from django.conf import settings
from curriculo.models import Tema

class Pregunta(models.Model):
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True, related_name='preguntas')
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='preguntas_creadas')
    enunciado = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pregunta {self.id} - {self.tema}"

class ImagenPregunta(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='evaluaciones/preguntas/')
    descripcion = models.CharField(max_length=255, blank=True, null=True, help_text="Descripción opcional (Ej: Figura 1)")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        
    def __str__(self):
        return f"Imagen para Pregunta {self.pregunta_id}"

class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name='opciones')
    texto = models.TextField(blank=True, null=True)
    imagen = models.ImageField(upload_to='evaluaciones/opciones/', blank=True, null=True)
    es_correcta = models.BooleanField(default=False)

    def __str__(self):
        return f"Opción de Pregunta {self.pregunta_id}"
