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

from django.utils import timezone
from datetime import datetime, time

class ClaseVirtual(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='clases_virtuales')
    titulo = models.CharField(max_length=200, help_text="Ej: Clase de Matemáticas - Ecuaciones")
    enlace = models.URLField()
    fecha = models.DateField(blank=True, null=True)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)

    def is_active_for_attendance(self):
        """
        Retorna True si la fecha y hora actual están dentro de la ventana de la clase.
        """
        if not self.fecha or not self.hora_inicio or not self.hora_fin:
            return False
            
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()
        
        if today == self.fecha:
            if self.hora_inicio <= current_time <= self.hora_fin:
                return True
        return False

    def __str__(self):
        return self.titulo
        
        
class Asistencia(models.Model):
    clase = models.ForeignKey(ClaseVirtual, on_delete=models.CASCADE, related_name='asistencias')
    alumno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asistencias')
    asistio = models.BooleanField(default=False)
    fecha_registro = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('clase', 'alumno')
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'

    def __str__(self):
        estado = "Presente" if self.asistio else "Ausente"
        return f"{self.alumno.username} - {self.clase.titulo}: {estado}"

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=ClaseVirtual)
def crear_registros_asistencia(sender, instance, created, **kwargs):
    """
    Cuando se crea una ClaseVirtual, matricular a todos los alumnos 
    con asistencia False por defecto.
    """
    if created:
        # Extraer a todos los usuarios con rol de estudiante o virtual
        alumnos = User.objects.filter(role__in=['student', 'virtual_student'], is_active=True)
        asistencias_a_crear = [
            Asistencia(clase=instance, alumno=alumno) 
            for alumno in alumnos
        ]
        if asistencias_a_crear:
            Asistencia.objects.bulk_create(asistencias_a_crear, ignore_conflicts=True)
