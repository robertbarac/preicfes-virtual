from django.db import models
from ubicaciones.models import Sede, Municipio


class Egreso(models.Model):
    ESTADO_EGRESO = [
        ('publicado', 'Publicado'),
        ('pagado', 'Pagado'),
    ]
    
    CONCEPTO_CHOICES = [
        ('nomina_profesores', 'Nómina profesores'),
        ('nomina_administrativos', 'Nómina administrativos'),
        ('arriendo', 'Arriendo'),
        ('nomina_vendedoras', 'Nómina vendedoras'),
        ('nomina_auxiliares', 'Nómina auxiliares'),
        ('servicios_publicos', 'Servicios públicos'),
        ('servicio_tecnico_pc', 'Servicio técnico PC'),
        ('servicio_tecnico_fotocopias', 'Servicio técnico fotocopias'),
        ('publicidad', 'Publicidad'),
        ('arreglo_planta_fisica', 'Arreglo planta física'),
        ('adquisiciones', 'Adquisiciones'),
        ('viaticos', 'Viáticos'),
        ('otros', 'Otros'),
    ]

    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name="egresos")
    municipio = models.ForeignKey('ubicaciones.Municipio', on_delete=models.CASCADE, related_name="egresos", null=True, blank=True)
    fecha = models.DateTimeField()  # Cambiado a DateTimeField
    concepto = models.CharField(max_length=100, choices=CONCEPTO_CHOICES, default='servicio_tecnico_pc')
    contratista = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_EGRESO, default='publicado')
    
    def save(self, *args, **kwargs):
        # Si no se ha especificado un municipio, usar el municipio de la sede
        if not self.municipio and self.sede and self.sede.municipio:
            self.municipio = self.sede.municipio
        # Si aún no hay municipio, intentar establecer Cartagena como predeterminado
        if not self.municipio:
            from ubicaciones.models import Municipio
            try:
                self.municipio = Municipio.objects.get(nombre='Cartagena')
            except Municipio.DoesNotExist:
                pass  # Si no existe Cartagena, dejarlo como None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Egreso de {self.concepto} - {self.estado}"
