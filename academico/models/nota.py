from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
# from .models import Clase, Alumno  # Importaciones locales de la misma app

class Nota(models.Model):
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE, related_name="notas")
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, related_name="notas")
    nota = models.DecimalField(
        max_digits=4, 
        decimal_places=1, 
        null=True, 
        blank=True,
        validators=[
            MinValueValidator(0),   # Valor mínimo permitido: 0
            MaxValueValidator(100)  # Valor máximo permitido: 100
        ]
    )
    def __str__(self):
        return f"Nota de {self.alumno} en {self.clase}: {self.nota if self.nota is not None else 'Sin nota'}"