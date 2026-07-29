# ubicaciones/models.py
from django.db import models

class Salon(models.Model):
    numero = models.PositiveIntegerField()
    capacidad_sillas = models.PositiveIntegerField(null=False)
    sede = models.ForeignKey('Sede', on_delete=models.CASCADE, related_name="salones")

    def __str__(self):
        return f"{self.sede.nombre} - Salón {self.numero}"