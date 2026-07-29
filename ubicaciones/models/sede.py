# ubicaciones/models.py
from django.db import models

class Sede(models.Model):
    nombre = models.CharField(max_length=100)
    municipio = models.ForeignKey('Municipio', on_delete=models.CASCADE, related_name="sedes")

    def __str__(self):
        return f"{self.nombre} - {self.municipio.nombre}"