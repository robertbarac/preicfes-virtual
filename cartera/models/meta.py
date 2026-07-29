from django.db import models

class MetaRecaudo(models.Model):
    MES_CHOICES = [
        (1, 'Enero'),
        (2, 'Febrero'),
        (3, 'Marzo'),
        (4, 'Abril'),
        (5, 'Mayo'),
        (6, 'Junio'),
        (7, 'Julio'),
        (8, 'Agosto'),
        (9, 'Septiembre'),
        (10, 'Octubre'),
        (11, 'Noviembre'),
        (12, 'Diciembre'),
    ]

    mes = models.IntegerField(choices=MES_CHOICES)
    anio = models.IntegerField()
    valor_meta = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('mes', 'anio')
        ordering = ['-anio', 'mes']

    def __str__(self):
        return f"Meta {self.get_mes_display()} {self.anio} - ${self.valor_meta:.1f}"
