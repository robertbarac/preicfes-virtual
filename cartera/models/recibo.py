from django.db import models
from .cuota import Cuota

class Recibo(models.Model):
    cuota = models.ForeignKey(Cuota, on_delete=models.CASCADE, related_name="recibos")
    numero_recibo = models.CharField(max_length=20, unique=True, help_text="Número único del recibo.")
    fecha_emision = models.DateTimeField(auto_now_add=True, help_text="Fecha de emisión del recibo.")
    monto_abonado = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monto abonado en este recibo.")
    metodo_pago = models.CharField(max_length=20, choices=Cuota.METODO_PAGO, help_text="Método de pago utilizado.")

    def __str__(self):
        return f"Recibo {self.numero_recibo} para {self.cuota}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cuota.agregar_abono(self.monto_abonado, self.metodo_pago)