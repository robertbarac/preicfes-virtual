from django.db import models
from django.utils import timezone

class AcuerdoPago(models.Model):
    ESTADO_ACUERDO = [
        ('emitido', 'Emitido'),
        ('cumplido', 'Cumplido'),
        ('incumplido', 'Incumplido'),
    ]

    cuota = models.ForeignKey('cartera.Cuota', on_delete=models.CASCADE, related_name="acuerdos")
    fecha_acuerdo = models.DateField(default=timezone.now, help_text="Fecha en que se crea el acuerdo.")
    fecha_prometida_pago = models.DateField(help_text="Fecha en que el alumno se compromete a pagar.")
    nota = models.TextField(blank=True, null=True, help_text="Observaciones sobre el acuerdo.")
    estado = models.CharField(max_length=20, choices=ESTADO_ACUERDO, default='emitido')

    class Meta:
        verbose_name = "Acuerdo de Pago"
        verbose_name_plural = "Acuerdos de Pago"
        ordering = ['-fecha_prometida_pago']

    def __str__(self):
        return f"Acuerdo para cuota {self.cuota.id} - Promesa: {self.fecha_prometida_pago}"
