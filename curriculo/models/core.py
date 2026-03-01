from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class HistorialCambios(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accion = models.CharField(max_length=50, help_text="Ej: Creación, Modificación, Eliminación")
    descripcion = models.TextField(help_text="Descripción del cambio realizado")
    fecha = models.DateTimeField(auto_now_add=True)
    
    # Generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.accion} por {self.usuario} en {self.fecha.strftime('%Y-%m-%d %H:%M')}"
class Materia(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Tema(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='temas')
    nombre = models.CharField(max_length=200)

    class Meta:
        ordering = ['materia__nombre', 'nombre']

    def __str__(self):
        return f"{self.materia.nombre} - {self.nombre}"

class Modulo(models.Model):
    """
    Representa una Semana o Módulo donde se agrupan contenidos, talleres y simulacros.
    """
    nombre = models.CharField(max_length=200, help_text="Ej: Semana 1, Módulo de Bienvenida")
    orden = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.nombre

class ClaseVirtual(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='clases_virtuales')
    titulo = models.CharField(max_length=200, help_text="Ej: Clase de Matemáticas - Ecuaciones")
    enlace = models.URLField()
    fecha_programada = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.titulo
