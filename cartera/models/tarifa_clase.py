from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class TarifaClase(models.Model):
    """
    Modelo para definir las tarifas de pago para las clases según diferentes criterios.
    """
    DIAS_SEMANA = [
        (0, 'Lunes a Viernes'),
        (1, 'Sábado'),
        (2, 'Domingo'),
    ]
    
    HORARIOS = [
        ('08:00-11:00', '8:00 AM - 11:00 AM'),
        ('14:00-17:00', '2:00 PM - 5:00 PM'),
        ('08:00-10:00', '8:00 AM - 10:00 AM'),
        ('10:00-12:00', '10:00 AM - 12:00 PM'),
        ('15:00-17:30', '3:00 PM - 5:30 PM'),
        ('18:45-20:45', '6:45 PM - 8:45 PM'),
        ('13:30-15:30', '1:30 PM - 3:30 PM'),
        ('15:30-17:30', '3:30 PM - 5:30 PM'),
        ('14:30-16:30', '2:30 PM - 4:30 PM'),
        ('16:30-18:30', '4:30 PM - 6:30 PM'),
        ('08:00-12:00', '8:00 AM - 12:00 PM (Medio Simulacro)'),
        ('08:00-17:00', '8:00 AM - 5:00 PM (Simulacro Completo)'),
        ('07:00-14:00', '7:00 AM - 2:00 PM (Jornada Especial Colegios)'),
    ]
    
    nombre = models.CharField(
        max_length=100, 
        help_text="Nombre descriptivo para esta tarifa"
    )
    tipo_dia = models.IntegerField(
        choices=DIAS_SEMANA, 
        help_text="Tipo de día al que aplica esta tarifa"
    )
    horario = models.CharField(
        max_length=20, 
        choices=HORARIOS, 
        help_text="Horario al que aplica esta tarifa",
        blank=True,
        null=True
    )
    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Valor a pagar por la clase en pesos colombianos"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activa = models.BooleanField(
        default=True, 
        help_text="Indica si esta tarifa está activa actualmente"
    )
    
    class Meta:
        verbose_name = "Tarifa de clase"
        verbose_name_plural = "Tarifas de clases"
        ordering = ['-activa', 'tipo_dia', 'horario']
        # Asegurar que no haya duplicados para la misma combinación de día y horario
        unique_together = ['tipo_dia', 'horario', 'activa']
    
    def clean(self):
        """Validaciones adicionales para el modelo"""
        # Verificar que no haya otra tarifa activa con la misma combinación de día y horario
        if self.activa:
            duplicadas = TarifaClase.objects.filter(
                tipo_dia=self.tipo_dia,
                horario=self.horario,
                activa=True
            ).exclude(pk=self.pk)
            
            if duplicadas.exists():
                raise ValidationError(
                    _('Ya existe una tarifa activa para este día y horario.')
                )
    
    def __str__(self):
        dia = dict(self.DIAS_SEMANA)[self.tipo_dia]
        horario_str = dict(self.HORARIOS).get(self.horario, 'Cualquier horario')
        return f"{self.nombre}: {dia} - {horario_str} - ${self.valor}"
    
    @classmethod
    def obtener_tarifa(cls, fecha, horario):
        """
        Obtiene la tarifa aplicable para una fecha y horario específicos.
        
        Args:
            fecha: Objeto date con la fecha de la clase
            horario: String con el horario en formato '08:00-10:00'
            
        Returns:
            Objeto TarifaClase o None si no se encuentra una tarifa aplicable
        """
        # Determinar si es fin de semana (5=sábado, 6=domingo)
        dia_semana = fecha.weekday()
        tipo_dia = 1 if dia_semana == 5 else 2 if dia_semana == 6 else 0
        
        # Buscar tarifa específica para ese día y horario
        try:
            return cls.objects.get(tipo_dia=tipo_dia, horario=horario, activa=True)
        except cls.DoesNotExist:
            # Si no hay tarifa específica para ese horario, buscar una genérica para ese día
            try:
                return cls.objects.get(tipo_dia=tipo_dia, horario__isnull=True, activa=True)
            except cls.DoesNotExist:
                return None
