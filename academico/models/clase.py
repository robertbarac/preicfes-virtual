from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.utils import timezone
from ubicaciones.models import Salon
from usuarios.models import User
# from . import Materia, Grupo  # Importaciones locales de la misma app


class Clase(models.Model):
    HORARIOS_DISPONIBLES = [
        ('08:00-11:00', '8:00 AM - 11:00 AM'),
        ('14:00-17:00', '2:00 PM - 5:00 PM'),
        ('08:00-10:00', '8:00 AM - 10:00 AM'),
        ('10:00-12:00', '10:00 AM - 12:00 PM'),
        ('15:00-17:30', '3:00 PM - 5:30 PM'),
        ('18:45-20:45', '6:45 PM - 8:45 PM'),
        ('13:30-15:30', '1:30 PM - 3:30 PM'),
        ('15:30-17:30', '3:30 PM - 5:30 PM'),
        ('14:30-16:30', '2:30 PM - 4:30 PM'),
        ('16:30-18:30', '4:30 PM - 6:30 PM'),
        ('08:00-12:00', '8:00 AM - 12:00 PM (Medio Simulacro)'),
        ('08:00-17:00', '8:00 AM - 5:00 PM (Simulacro Completo)'),
        ('07:00-14:00', '7:00 AM - 2:00 PM (Jornada Especial Colegios)'),
    ]

    ESTADO_CLASE = [
        ('programada', 'Programada'),
        ('vista', 'Vista'),
        ('cancelada', 'Cancelada'),
    ]

    fecha = models.DateField()
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="clases")
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name="clases")
    profesor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clases",
        limit_choices_to={'groups__name': 'Profesor'},  # Solo usuarios del grupo "Profesor"
        null=True,
        blank=True
    )
    grupo = models.ForeignKey('Grupo', on_delete=models.CASCADE, related_name="clases")
    horario = models.CharField(max_length=20, choices=HORARIOS_DISPONIBLES, help_text="Seleccione el horario de la clase.", default=None)
    estado = models.CharField(max_length=20, choices=ESTADO_CLASE, default='programada', help_text="Estado de la clase.")
    taller = models.ForeignKey(
        'evaluaciones.Taller',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clases_presenciales',
        help_text="Taller interactivo opcional asignado a esta clase presencial."
    )
    taller_cerrado = models.BooleanField(
        default=False,
        help_text="True cuando el docente realiza el corte y cierra la recepción de respuestas del taller presencial."
    )
    taller_notas_liberadas = models.BooleanField(
        default=False,
        help_text="True cuando el docente libera las notas y solucionario para los estudiantes."
    )


    def clean(self):
        # Solo realizar validaciones de profesor si se ha asignado uno
        if self.profesor:
            # Validación 1: El profesor debe pertenecer al grupo "Profesor"
            if not self.profesor.groups.filter(name="Profesor").exists():
                raise ValidationError({'profesor': 'El usuario seleccionado no pertenece al grupo de Profesores.'})

            # Validación 3: Evitar superposición de horarios para el mismo profesor
            clases_profesor = Clase.objects.filter(
                profesor=self.profesor,
                fecha=self.fecha,
                horario=self.horario
            ).exclude(id=self.id)

            if clases_profesor.exists():
                raise ValidationError({
                    'horario': f'El profesor {self.profesor.get_full_name()} ya tiene una clase asignada en este horario.'
                })

        # Validación 2: Evitar superposición de horarios para el mismo salón
        clases_existentes = Clase.objects.filter(
            salon=self.salon,
            fecha=self.fecha,
            horario=self.horario
        ).exclude(id=self.id)

        if clases_existentes.exists():
            raise ValidationError({'horario': 'El salón ya está ocupado en este horario.'})


    def get_hora_inicio(self):
        """Obtiene la hora de inicio como objeto time"""
        hora_str = self.horario.split('-')[0].strip()
        # Asegurar formato HH:MM agregando cero inicial si es necesario
        if len(hora_str.split(':')[0]) == 1:
            hora_str = f'0{hora_str}'
        return datetime.strptime(hora_str, '%H:%M').time()
        
    def get_hora_fin(self):
        """Obtiene la hora de fin como objeto time"""
        hora_str = self.horario.split('-')[1].strip()
        # Asegurar formato HH:MM agregando cero inicial si es necesario
        if len(hora_str.split(':')[0]) == 1:
            hora_str = f'0{hora_str}'
        return datetime.strptime(hora_str, '%H:%M').time()
        
    def get_datetime_fin(self):
        """Combina fecha y hora de fin como datetime aware"""
        return timezone.make_aware(
            datetime.combine(self.fecha, self.get_hora_fin())
        )
    
    def get_datetime_inicio(self):
        """Combina fecha y hora de inicio como datetime aware"""
        return timezone.make_aware(
            datetime.combine(self.fecha, self.get_hora_inicio())
        )
    
    def puede_registrar_asistencia(self, usuario):
        """
        Determina si un usuario puede registrar asistencia
        - Superusuarios y SecretariaAcademica siempre pueden
        - Profesores solo pueden ±5 minutos alrededor de la hora de clase
        
        Args:
            usuario: El usuario que intenta registrar asistencia
        """
        if usuario.is_superuser or usuario.groups.filter(name='SecretariaAcademica').exists():
            return True
            
        if usuario != self.profesor:
            return False
            
        # Para el profesor, verificar el margen de tiempo
        ahora = timezone.localtime(timezone.now())  # Convertir a hora local
        inicio_clase = timezone.localtime(self.get_datetime_inicio())  # Asegurar que esté en hora local
        fin_clase = timezone.localtime(self.get_datetime_fin())  # Hora de fin en local
        margen = timedelta(minutes=60)
        
        # Permitir registro durante toda la clase, incluyendo 5 minutos antes y 5 minutos después
        puede = (inicio_clase - margen) <= ahora <= (fin_clase + margen)
            
        return puede

    def __str__(self):
        return f"Clase de {self.materia.nombre} - {self.fecha} ({self.get_horario_display()})"
