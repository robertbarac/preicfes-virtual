# ubicaciones/models.py
from django.db import models

class Municipio(models.Model):
    nombre = models.CharField(max_length=30)
    departamento = models.ForeignKey('Departamento', on_delete=models.CASCADE, related_name="ciudades")

    def __str__(self):
        return f"{self.nombre} - {self.departamento.nombre}"
