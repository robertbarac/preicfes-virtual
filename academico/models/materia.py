from django.db import models

class Materia(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return str(self.nombre)
