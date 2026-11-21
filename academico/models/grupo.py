from django.db import models
from ubicaciones.models import Salon

class Grupo(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="grupos")
    codigo = models.CharField(max_length=20, unique=True, blank=True, help_text="""Regla de código:
                            3 letras de la ciudad + 3 letras de la sede + codigo de 2 numeros + una letra 
                            (opcional por si) hay un salon gemelo""")

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = (
                f"{self.salon.sede.municipio.departamento.nombre[:3]}"  # 3 iniciales del departamento
                f"{self.salon.sede.municipio.nombre[:3]}"  # 3 iniciales de la ciudad
                f"{self.salon.sede.nombre[:3]}"  # 3 iniciales de la sede
                f"{self.id:02d}"  # Número de dos dígitos
            )
        super().save(*args, **kwargs)

    def obtener_alumnos(self):
        """Retorna todos los alumnos pertenecientes a este grupo (como grupo principal o secundario)."""
        from django.db.models import Q
        from .alumno import Alumno
        return Alumno.objects.filter(
            Q(grupo_actual=self) | Q(grupo_secundario=self)
        ).distinct().order_by('primer_apellido', 'segundo_apellido', 'nombres')

    def __str__(self):
        return f"{self.codigo} - {self.salon.sede.nombre}"