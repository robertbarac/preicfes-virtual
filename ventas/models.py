from django.db import models
from django.conf import settings
from django.utils import timezone
import os
import uuid

class Vendedor(models.Model):
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class PreVenta(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preventas',
        verbose_name="Vendedor / Autor"
    )
    nombre_padre_madre = models.CharField(
        max_length=150,
        verbose_name="Nombre Padre/Madre"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )
    nombre_estudiante = models.CharField(
        max_length=150,
        verbose_name="Nombre del Estudiante"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )

    class Meta:
        verbose_name = "Preventa"
        verbose_name_plural = "Preventas"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Preventa: {self.nombre_estudiante} (Acudiente: {self.nombre_padre_madre})"


class Incidencia(models.Model):
    ETAPA_CHOICES = [
        ('contacto_inicial', 'Contacto Inicial'),
        ('presentacion', 'Presentación del Servicio'),
        ('seguimiento', 'Seguimiento'),
        ('cierre_exitoso', 'Cierre Exitoso / Matriculado'),
        ('descartado', 'Descartado'),
    ]

    preventa = models.ForeignKey(
        PreVenta,
        on_delete=models.CASCADE,
        related_name='incidencias',
        verbose_name="Preventa Asociada"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='incidencias_registradas',
        verbose_name="Registrado por"
    )
    fecha = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y Hora de la Incidencia"
    )
    etapa = models.CharField(
        max_length=50,
        choices=ETAPA_CHOICES,
        default='contacto_inicial',
        verbose_name="Etapa"
    )
    texto = models.TextField(
        verbose_name="Detalle de la Incidencia"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )

    class Meta:
        verbose_name = "Incidencia"
        verbose_name_plural = "Incidencias"
        ordering = ['-fecha']

    def __str__(self):
        local_date = timezone.localtime(self.fecha).strftime('%d/%m/%Y %I:%M %p')
        return f"Incidencia de {self.get_etapa_display()} - {local_date} (por {self.user.username})"

    @property
    def es_editable(self):
        """
        Determina si la incidencia se puede editar/eliminar por un usuario normal.
        Solo se permite si la fecha local de la incidencia coincide con la fecha local actual.
        """
        local_incidencia_date = timezone.localtime(self.fecha).date()
        local_current_date = timezone.localtime(timezone.now()).date()
        return local_incidencia_date == local_current_date


def incidencia_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    return os.path.join('preventas', 'incidencias', unique_name)


def incidencia_imagen_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    return os.path.join('preventas', 'incidencias', unique_name)


class IncidenciaImagen(models.Model):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name="Incidencia"
    )
    imagen = models.ImageField(
        upload_to=incidencia_imagen_upload_path,
        verbose_name="Imagen de Evidencia"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )

    class Meta:
        verbose_name = "Imagen de Incidencia"
        verbose_name_plural = "Imágenes de Incidencia"
        ordering = ['fecha_creacion']

    def __str__(self):
        return f"Imagen para incidencia ID {self.incidencia.id}"
