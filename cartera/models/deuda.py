from django.db import models
from django.core.exceptions import ValidationError
from academico.models import Alumno

class Deuda(models.Model):
    ESTADO_DEUDA = [
        ('emitida', 'Emitida'),
        ('pagada', 'Pagada'),
    ]
    
    alumno = models.OneToOneField(Alumno, on_delete=models.CASCADE, related_name="deuda")
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor total de la deuda.")
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Saldo pendiente de la deuda.")
    fecha_creacion = models.DateTimeField(auto_now_add=True, help_text="Fecha de creación de la deuda.")
    estado = models.CharField(max_length=20, choices=ESTADO_DEUDA, default='emitida', help_text="Estado actual de la deuda.")
    edicion_habilitada = models.BooleanField(default=False, help_text="Indica si la deuda puede ser editada.")

    def __str__(self):
        return str(f"Deuda de {self.alumno} - {self.estado}")

    def clean(self):
        """Validar que el estado 'pagada' no pueda ser asignado manualmente sin cumplir las condiciones."""
        super().clean()
        if self.estado == 'pagada':
            cuotas_count = self.cuotas.count()
            total_abonado = self.cuotas.aggregate(models.Sum('monto_abonado'))['monto_abonado__sum'] or 0
            
            # Verificar las condiciones para estado pagada
            if not (self.saldo_pendiente == 0 and cuotas_count > 0 and total_abonado >= self.valor_total):
                raise ValidationError({
                    'estado': 'Una deuda solo puede marcarse como pagada cuando tiene cuotas asociadas '
                             'con abonos que sumen el valor total. Use el proceso de pagos por cuotas.'
                })

    def save(self, *args, **kwargs):
        """Sobreescribir el método save para asegurar que el estado se actualice correctamente."""
        # Si se está intentando marcar como pagada directamente, forzar recálculo
        if self.estado == 'pagada':
            update_fields = kwargs.get('update_fields')
            
            # Solo realizar esta validación si no viene del método actualizar_saldo_y_estado
            if not update_fields or 'saldo_pendiente' not in update_fields:
                cuotas_count = self.cuotas.count()
                total_abonado = self.cuotas.aggregate(models.Sum('monto_abonado'))['monto_abonado__sum'] or 0
                
                # Verificar condiciones y forzar estado correcto
                if not (cuotas_count > 0 and total_abonado >= self.valor_total):
                    self.estado = 'emitida'
                else:
                    # Actualizar el saldo pendiente si hay abonos
                    self.saldo_pendiente = max(0, self.valor_total - total_abonado)
        
        super().save(*args, **kwargs)

    def actualizar_saldo_y_estado(self):
        """Recalcula el saldo pendiente y actualiza el estado de la deuda.
        Verifica que existan cuotas asociadas y que la suma de sus abonos sea igual al valor total
        para marcar como pagada."""
        # Verificar si existen cuotas asociadas
        cuotas_count = self.cuotas.count()
        
        # Calcular el total abonado
        total_abonado = self.cuotas.aggregate(models.Sum('monto_abonado'))['monto_abonado__sum'] or 0
        self.saldo_pendiente = self.valor_total - total_abonado

        # Actualizar estado - solo marcar como pagada si:
        # 1. El saldo pendiente es 0
        # 2. Existen cuotas asociadas
        # 3. La suma de los montos abonados es igual al valor total
        if self.saldo_pendiente <= 0 and cuotas_count > 0 and total_abonado >= self.valor_total:
            self.saldo_pendiente = 0  # Asegurar que no quede negativo
            self.estado = "pagada"
        else:
            self.estado = "emitida"

        # Usar el update_fields para indicar que viene desde este método
        self.save(update_fields=['saldo_pendiente', 'estado'])