from django.db import models
from django.conf import settings

class Inasistencia(models.Model):
    """Registra y justifica la inasistencia de un alumno a una clase específica."""
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE, related_name="inasistencias", blank=True, null=True)
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, related_name="inasistencias")
    motivo = models.TextField(
        help_text="Razón de la inasistencia (ej. cita médica, calamidad, etc.)",
        blank=True,
        null=True
    )
    justificada = models.BooleanField(
        default=False, 
        help_text="Marcar si la inasistencia fue justificada con un soporte válido."
    )
    soporte = models.ImageField(
        upload_to='soportes_inasistencias/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Imagen de soporte para la justificación (ej. excusa médica)."
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="inasistencias_registradas"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inasistencia"
        verbose_name_plural = "Inasistencias"
        ordering = ['-clase__fecha', 'alumno']
        unique_together = ('clase', 'alumno') # Un alumno solo puede tener una inasistencia por clase

    def __str__(self):
        return f"Inasistencia de {self.alumno} en {self.clase}"
