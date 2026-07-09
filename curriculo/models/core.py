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
class Programa(models.Model):
    """Representa una oferta educativa (PreICFES, Inglés, Bachillerato, …)."""
    TIPOS = (
        ('preicfes',     'PreICFES'),
        ('ingles',       'Inglés'),
        ('bachillerato', 'Bachillerato por Ciclos'),
    )
    nombre      = models.CharField(max_length=100)
    tipo        = models.CharField(max_length=20, choices=TIPOS, default='preicfes')
    slug        = models.SlugField(unique=True)
    activo      = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Programa'
        verbose_name_plural = 'Programas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Ciclo(models.Model):
    """Período o nivel dentro de un Programa (ej: Ciclo 2025, Nivel A1)."""
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE,
                                  related_name='ciclos')
    nombre   = models.CharField(max_length=200)
    orden    = models.PositiveIntegerField(default=0)
    visible  = models.BooleanField(default=True,
                  help_text="Si está visible para los estudiantes del programa")

    class Meta:
        ordering = ['orden']
        verbose_name = 'Ciclo'
        verbose_name_plural = 'Ciclos'

    def __str__(self):
        return f"{self.programa.nombre} — {self.nombre}"


class Materia(models.Model):
    programas   = models.ManyToManyField(
        Programa, related_name='materias', blank=True,
        help_text="Programas en los que se usa esta materia"
    )
    nombre      = models.CharField(max_length=200)
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
    Semana o Módulo que agrupa contenidos, talleres, simulacros y ejercicios.
    Pertenece a un Ciclo (que a su vez pertenece a un Programa).
    """
    ciclo       = models.ForeignKey(Ciclo, on_delete=models.CASCADE,
                                     related_name='modulos',
                                     null=True,   # temporal: RunPython rellenará esto
                                     blank=True)
    nombre      = models.CharField(max_length=200, help_text="Ej: Semana 1, Módulo de Bienvenida")
    orden       = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(blank=True, null=True)
    activo      = models.BooleanField(default=True, help_text="Si está desmarcado, los estudiantes no podrán ver este módulo.")

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.nombre

    @property
    def programa(self):
        """Acceso conveniente al programa a través del ciclo."""
        return self.ciclo.programa if self.ciclo_id else None

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
from django.core.cache import cache

User = get_user_model()

@receiver(post_save, sender=ClaseVirtual)
def crear_registros_asistencia(sender, instance, created, **kwargs):
    """
    Cuando se crea una ClaseVirtual, matricular a todos los alumnos 
    con asistencia False por defecto.
    """
    if created:
        # Extraer a todos los usuarios con rol de estudiante o virtual
        programa_id = instance.modulo.ciclo_id and instance.modulo.ciclo.programa_id
        if programa_id:
            alumnos = User.objects.filter(
                programa_id=programa_id,
                role__in=['student', 'virtual_student'],
                is_active=True
            ).distinct()
        else:
            alumnos = User.objects.filter(role__in=['student', 'virtual_student'], is_active=True)
        asistencias_a_crear = [
            Asistencia(clase=instance, alumno=alumno) 
            for alumno in alumnos
        ]
        if asistencias_a_crear:
            Asistencia.objects.bulk_create(asistencias_a_crear, ignore_conflicts=True)


# ─── Invalidación de caché ────────────────────────────────────────────────────
from curriculo.cache_keys import PROGRAMA_CACHE_KEY

def _invalidar_programa_cache():
    """Borra el caché compartido del programa."""
    cache.delete(PROGRAMA_CACHE_KEY)


@receiver(post_save, sender=ClaseVirtual)
def invalidar_cache_por_clase_virtual(sender, instance, **kwargs):
    """
    Borra el caché cuando se crea o edita una ClaseVirtual
    (puede haber cambiado fecha, hora o enlace).
    """
    _invalidar_programa_cache()


@receiver(post_save, sender=Modulo)
def invalidar_cache_por_modulo(sender, instance, **kwargs):
    """
    Borra el caché cuando se crea o edita un Módulo.
    """
    _invalidar_programa_cache()

