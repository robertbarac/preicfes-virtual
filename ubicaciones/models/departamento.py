# ubicaciones/models.py
from django.db import models

class Departamento(models.Model):
    nombre = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.nombre
