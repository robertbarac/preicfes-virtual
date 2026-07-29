from django.db import models
from django.utils.timezone import now
from django.utils import timezone
from .deuda import Deuda
from .acuerdo_pago import AcuerdoPago
from django.core.exceptions import ValidationError
from datetime import date

class Cuota(models.Model):
    ESTADO_CUOTA = [
        ('emitida', 'Emitida'),
        ('pagada_parcial', 'Pagada Parcial'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
    ]

    METODO_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('datáfono', 'Datáfono'),
    ]

    deuda = models.ForeignKey('Deuda', on_delete=models.CASCADE, related_name="cuotas")
    monto = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monto total de la cuota.")
    monto_abonado = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Monto abonado hasta la fecha.")
    fecha_vencimiento = models.DateField(help_text="Fecha de vencimiento de la cuota.")
    fecha_pago = models.DateField(blank=True, null=True, help_text="Fecha en que se realizó el pago efectivamente.")
    estado = models.CharField(max_length=20, choices=ESTADO_CUOTA, default='emitida', help_text="Estado actual de la cuota.")
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO, blank=True, null=True, help_text="Método de pago utilizado.")
    soporte_pago = models.ImageField(
        upload_to='soportes_cuotas/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name="Soporte de Pago",
        help_text="Imagen de soporte o comprobante de la transacción de pago."
    )

    # Auditoría de ediciones
    editado_por = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Editado por",
        help_text="Username del usuario que realizó la última edición."
    )
    fecha_edicion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de edición",
        help_text="Fecha y hora de la última edición."
    )

    def clean(self):
        """Validaciones personalizadas para el modelo Cuota."""
        super().clean()
        if self.fecha_pago:
            today = timezone.localtime(timezone.now()).date()

            # Validación: La fecha de pago no puede ser una fecha futura.
            if self.fecha_pago > today:
                raise ValidationError({
                    'fecha_pago': 'La fecha de pago no puede ser una fecha futura.'
                })

    def __str__(self):
        return f"Cuota de {self.monto} - {self.estado} (Vence: {self.fecha_vencimiento})"

    def actualizar_estado(self):
        """Cambia el estado de la cuota según el monto abonado y la fecha de vencimiento."""
        if self.monto_abonado >= self.monto:
            self.estado = "pagada"
        elif self.monto_abonado > 0:
            self.estado = "pagada_parcial"
        elif now().date() > self.fecha_vencimiento:
            self.estado = "vencida"
        else:
            self.estado = "emitida"

    def save(self, run_logic=True, *args, **kwargs):
        """Guarda la cuota. Si run_logic es True, ejecuta la lógica de actualización de estado y deuda."""
        if run_logic:
            # Si se está realizando un pago y no hay fecha_pago registrada, establecerla ahora
            if self.monto_abonado > 0 and not self.fecha_pago:
                self.fecha_pago = timezone.localtime(now()).date()
            self.actualizar_estado()

        # Validación estricta para evitar guardar pagos con fechas futuras en la base de datos
        if self.fecha_pago:
            today = timezone.localtime(timezone.now()).date()
            if self.fecha_pago > today:
                raise ValidationError({
                    'fecha_pago': 'La fecha de pago no puede ser una fecha futura.'
                })

        super().save(*args, **kwargs)

        if run_logic:
            # Si se realiza un pago (parcial o total), buscar y cumplir el acuerdo activo.
            # Esta lógica debe ir DESPUÉS de super().save() para que self.id exista.
            if self.monto_abonado > 0 and self.estado in ['pagada', 'pagada_parcial']:
                acuerdo_activo = self.acuerdos.filter(estado='emitido').order_by('-fecha_acuerdo').first()
                if acuerdo_activo:
                    acuerdo_activo.estado = 'cumplido'
                    acuerdo_activo.save()

            self.deuda.actualizar_saldo_y_estado()

    def delete(self, *args, **kwargs):
        """Si se elimina una cuota, se recalcula el saldo pendiente de la deuda."""
        super().delete(*args, **kwargs)
        self.deuda.actualizar_saldo_y_estado()
