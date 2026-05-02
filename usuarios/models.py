from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from datetime import timedelta

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('virtual_student', 'VirtualStudent'),
    )
    # Admin role is handled by is_superuser and is_staff boolean properties inherited from AbstractUser
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    email = models.EmailField('email address', unique=True)
    
    # Identificación para Pico y Cédula
    TIPO_DOC_CHOICES = (
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PAS', 'Pasaporte'),
    )
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOC_CHOICES, default='CC')
    first_name = models.CharField('first name', max_length=150, blank=False, null=False)
    last_name = models.CharField('last name', max_length=150, blank=False, null=False)

    numero_documento = models.CharField(
        max_length=20, 
        blank=False, 
        null=False, 
        unique=True, 
        validators=[RegexValidator(regex=r'^\d+$', message='El número de documento solo debe contener números, sin puntos ni espacios.')],
        help_text="Número de identificación legal"
    )

    telefono = models.CharField(
        max_length=10,
        blank=False,
        null=False,
        validators=[RegexValidator(regex=r'^\d{10}$', message='El teléfono debe tener exactamente 10 dígitos, sin comas, puntos ni espacios.')],
        help_text="Número de teléfono celular (10 dígitos)"
    )
    
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

class WhatsAppResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_reset_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        ahora = timezone.now()
        tiempo_transcurrido = ahora - self.created_at
        return not self.is_used and tiempo_transcurrido <= timedelta(minutes=5)

    def __str__(self):
        return f"Código {self.code} para {self.user.username} (Usado: {self.is_used})"
