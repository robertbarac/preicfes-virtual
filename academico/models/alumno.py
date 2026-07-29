from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from ubicaciones.models import Municipio
from ventas.models import Vendedor
from . import Grupo  # Importación relativa del modelo Grupo en la misma app


class Alumno(models.Model):
    TIPO_IDENTIFICACION = [
        ('TI', 'Tarjeta de Identidad'),
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
    ]
    
    ESTADO_ALUMNO = [
        ('activo', 'Activo'),
        ('retirado', 'Retirado'),
        ('limbo', 'Limbo'),
    ]
    
    TIPO_PROGRAMA = [
        ('pre_privado', 'PreICFES Privado'),
        ('pre_publico', 'PreICFES Público'),
        ('formacion_laboral', 'Formación Laboral'),
        ('preicfes_kids', 'PreICFES Kids'),
        ('preicfes_virtual', 'PreICFES Virtual'),
        ('preicfes_vacacional', 'PreICFES Vacacional'),
        ('bachillerato_por_ciclos', 'Bachillerato por ciclos'),
        ('curso_ingles', 'Curso de Inglés')
    ]

    # Campos obligatorios
    nombres = models.CharField(max_length=100)
    primer_apellido = models.CharField(max_length=100)
    segundo_apellido = models.CharField(max_length=100, blank=True, null=True)
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    identificacion = models.CharField(
        max_length=20, 
        help_text="Identificación del alumno (solo números, NO PUNTOS, NO COMAS, NO ESPACIOS)"
    )
    tipo_identificacion = models.CharField(max_length=2, choices=TIPO_IDENTIFICACION, default='TI')
    tipo_programa = models.CharField(
        max_length=30, 
        choices=TIPO_PROGRAMA, 
        default='pre_privado',
        verbose_name="Tipo de Programa",
        help_text="Programa al que pertenece el estudiante"
    )
    es_becado = models.BooleanField(
        default=False,
        verbose_name="¿Es becado?",
        help_text="Marcar si el estudiante tiene beca"
    )

    FRECUENCIA_PAGO = [
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ]

    frecuencia_pago = models.CharField(
        max_length=20,
        choices=FRECUENCIA_PAGO,
        verbose_name="Frecuencia de Pago",
        help_text="Frecuencia con la que el estudiante realiza los pagos"
    )

    # Fechas de ingreso y culminación
    fecha_ingreso = models.DateField(
        default=date(2025, 1, 1),
        verbose_name="Fecha de ingreso",
        help_text="Fecha en que el alumno ingresó al preicfes"
    )
    fecha_culminacion = models.DateField(
        default=date(2025, 8, 8),
        verbose_name="Fecha de culminación",
        help_text="Fecha en que el alumno culmina su estancia en el preicfes"
    )
    
    # Contacto
    celular = models.CharField(max_length=15, default='SIN DATOS')

    # Datos del padre
    nombres_padre = models.CharField(max_length=100, default='SIN DATOS')
    primer_apellido_padre = models.CharField(max_length=100, default='SIN DATOS')
    segundo_apellido_padre = models.CharField(max_length=100, default='SIN DATOS')
    celular_padre = models.CharField(max_length=15, default='SIN DATOS')

    # Datos de la madre
    nombres_madre = models.CharField(max_length=100, default='SIN DATOS')
    primer_apellido_madre = models.CharField(max_length=100, default='SIN DATOS')
    segundo_apellido_madre = models.CharField(max_length=100, default='SIN DATOS')
    celular_madre = models.CharField(max_length=15, default='SIN DATOS')

    # Estado del alumno
    estado = models.CharField(
        max_length=10, 
        choices=ESTADO_ALUMNO, 
        default='activo',
        verbose_name="Estado",
        help_text="Estado actual del alumno en el preicfes"
    )
    fecha_retiro = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Fecha de retiro",
        help_text="Fecha en que el alumno se retiró del preicfes"
    )
    
    # Relaciones
    usuario = models.OneToOneField(
        'usuarios.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="perfil_alumno",
        help_text="Cuenta de acceso del estudiante a la plataforma virtual"
    )
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="alumnos")
    grupo_actual = models.ForeignKey(Grupo, on_delete=models.PROTECT, related_name="alumnos_actuales")
    vendedor = models.ForeignKey(
        Vendedor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="alumnos",
        verbose_name="Vendedor"
    )

    def clean(self):
        super().clean()
        try:
            if self.grupo_actual_id and self.grupo_actual and self.municipio:
                if self.grupo_actual.salon.sede.municipio != self.municipio:
                    raise ValidationError({'grupo_actual': 'El grupo seleccionado no pertenece al municipio del alumno.'})
        except Exception:
            pass

        if self.identificacion:
            ident_clean = str(self.identificacion).strip()
            qs = Alumno.objects.filter(identificacion=ident_clean)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'identificacion': f'Ya existe un alumno registrado con la identificación {ident_clean}.'})

    def get_full_name(self):
        apellidos = f"{self.primer_apellido} {self.segundo_apellido or ''}".strip()
        return f"{self.nombres} {apellidos}".strip()

    def __str__(self):
        return f"{self.nombres} {self.primer_apellido} ({self.identificacion}) - {self.municipio.nombre}"
