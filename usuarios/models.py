from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('virtual_student', 'VirtualStudent'),
    )
    # Admin role is handled by is_superuser and is_staff boolean properties inherited from AbstractUser
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    # Identificación para Pico y Cédula
    TIPO_DOC_CHOICES = (
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PAS', 'Pasaporte'),
    )
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOC_CHOICES, default='CC')
    numero_documento = models.CharField(max_length=20, blank=True, null=True, unique=True, help_text="Número de identificación legal")
    
    creador = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_registrados', help_text="Usuario que registró a esta persona (ej. Admin/Secretaría)")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

from django.utils import timezone

class VentanaRegistro(models.Model):
    fecha_inicio = models.DateTimeField(help_text="Fecha y hora de inicio de apertura")
    fecha_fin = models.DateTimeField(help_text="Fecha y hora de cierre")
    creador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ventanas_creadas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def is_active(self):
        now = timezone.now()
        return self.fecha_inicio <= now <= self.fecha_fin

    def __str__(self):
        estado = "ACTIVA" if self.is_active() else "CERRADA"
        return f"Ventana {self.id} ({estado}) - {self.fecha_inicio.strftime('%Y-%m-%d %H:%M')} a {self.fecha_fin.strftime('%Y-%m-%d %H:%M')}"
