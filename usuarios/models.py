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
    
    # Asignaciones de Programas (Directas)
    programa = models.ForeignKey(
        'curriculo.Programa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudiantes_inscritos',
        help_text="Programa asignado al estudiante (rol: student/virtual_student)"
    )
    programas_docente = models.ManyToManyField(
        'curriculo.Programa',
        blank=True,
        related_name='profesores_inscritos',
        help_text="Programas a los que el profesor tiene acceso (rol: teacher)"
    )
    
    email = models.EmailField('email address', unique=True, null=True, blank=True)
    
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
        blank=True, 
        null=True, 
        unique=True, 
        validators=[RegexValidator(regex=r'^\d+$', message='El número de documento solo debe contener números, sin puntos ni espacios.')],
        help_text="Número de identificación legal"
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Número de teléfono celular"
    )
    
    creador = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_registrados', help_text="Usuario que registró a esta persona (ej. Admin/Secretaría)")

    # Ubicaciones y Sedes (Fusión Cartera)
    municipio = models.ForeignKey('ubicaciones.Municipio', on_delete=models.SET_NULL, related_name='usuarios', blank=True, null=True)
    departamento = models.ForeignKey('ubicaciones.Departamento', on_delete=models.SET_NULL, related_name='usuarios', blank=True, null=True)
    sede = models.ForeignKey('ubicaciones.Sede', on_delete=models.SET_NULL, related_name='usuarios', blank=True, null=True)

    @property
    def is_observador(self):
        return self.groups.filter(name__in=['Observador', 'ObservadorColegio']).exists()

    @property
    def es_docente(self):
        """True si el usuario es docente por role o por grupo Profesor/Teacher."""
        if self.role == 'teacher':
            return True
        return self.groups.filter(name__in=['Profesor', 'Teacher']).exists()

    @property
    def es_personal_gestion(self):
        """
        Retorna True si el usuario pertenece al personal administrativo / de gestión académica y cartera
        (SecretariaCartera, SecretariaAcademica, CoordinadorDepartamental, Auxiliar, ObservadorColegio)
        y NO es docente ni superusuario.
        """
        if self.is_superuser or self.role == 'teacher':
            return False
        group_names = set(self.groups.values_list('name', flat=True))
        if 'Profesor' in group_names or 'Teacher' in group_names:
            return False
        return bool(group_names.intersection({
            'SecretariaCartera', 'SecretariaAcademica', 'CoordinadorDepartamental', 'Auxiliar', 'ObservadorColegio'
        }) or self.is_staff)

    @property
    def es_estudiante(self):
        """True si el usuario es estudiante por grupo Student/VirtualStudent o por falta de roles administrativos."""
        if self.groups.filter(name__in=['Student', 'VirtualStudent']).exists():
            return True
        if self.is_superuser or self.is_staff or self.es_docente or self.is_observador:
            return False
        return True

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

class ConfiguracionPlataforma(models.Model):
    THEME_CHOICES = (
        ('teal',          'Original (Oscuro-Teal)'),
        ('gold',          'Proyecto 500 (Negro-Dorado)'),
        ('christmas',     'Navidad (Rojo-Verde)'),
        ('franciainglat', 'Francia vs Inglaterra'),
        ('espanaarg',     'España vs Argentina'),
    )
    tema_menu = models.CharField(
        max_length=20, 
        choices=THEME_CHOICES, 
        default='teal', 
        help_text="Paleta de colores para el menú lateral."
    )
    
    class Meta:
        verbose_name = "Configuración de la Plataforma"
        verbose_name_plural = "Configuraciones de la Plataforma"

    def __str__(self):
        return f"Configuración Activa ({self.get_tema_menu_display()})"


# ─── Invalidación de caché ────────────────────────────────────────────────────
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

@receiver([post_save, post_delete], sender=ConfiguracionPlataforma)
def invalidar_tema_menu_cache(sender, instance, **kwargs):
    cache.delete('tema_menu_global')

from django.db.models.signals import pre_save

@receiver(pre_save, sender=User)
def sanitizar_user_fields(sender, instance, **kwargs):
    if instance.email == "":
        instance.email = None
    if instance.numero_documento == "":
        instance.numero_documento = None


import os
from django.core.exceptions import ValidationError

def firma_upload_path(instance, filename):
    """Define la ruta donde se guardarán las firmas digitales"""
    ext = filename.split('.')[-1]
    filename = f"{instance.usuario.username}.{ext}"
    return os.path.join('firmas', filename)


class Firma(models.Model):
    """Modelo para almacenar las firmas digitales de los usuarios del staff"""
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='firma')
    imagen = models.ImageField(upload_to=firma_upload_path, help_text="Imagen de la firma digital (PNG transparente)")
    
    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmas"
    
    def __str__(self):
        return f"Firma de {self.usuario.get_full_name() or self.usuario.username}"
    
    def clean(self):
        if not self.usuario.is_staff:
            raise ValidationError({'usuario': 'Solo los usuarios del staff pueden tener firmas registradas.'})
        if self.imagen:
            ext = self.imagen.name.split('.')[-1].lower()
            if ext not in ['png', 'jpg', 'jpeg']:
                raise ValidationError({'imagen': 'El archivo debe ser una imagen PNG, JPG o JPEG.'})
