from django.db import models
# from .models import Clase, Alumno  # Importaciones locales de la misma app


class Asistencia(models.Model):
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE, related_name="asistencias")
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, related_name="asistencias")
    asistio = models.BooleanField(default=False)

    def __str__(self):
        return f"Asistencia de {self.alumno} en {self.clase}: {'Sí' if self.asistio else 'No'}"