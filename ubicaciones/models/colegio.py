# ubicaciones/models/colegio.py
from django.db import models


class Colegio(models.Model):
    nombre = models.CharField(max_length=150)
    municipio = models.ForeignKey(
        'Municipio',
        on_delete=models.CASCADE,
        related_name='colegios',
    )
    class Meta:
        ordering = ['municipio__departamento__nombre', 'municipio__nombre', 'nombre']
        unique_together = ('nombre', 'municipio')
        verbose_name = 'Colegio'
        verbose_name_plural = 'Colegios'

    def __str__(self):
        return f"{self.nombre} ({self.municipio.nombre} - {self.municipio.departamento.nombre})"
