from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# Orden de componentes por defecto (válido para simulacros actuales)
_DEFAULT_COMPONENTES_S1 = ["matematicas", "lectura", "sociales", "naturales"]
_DEFAULT_COMPONENTES_S2 = ["sociales", "matematicas", "naturales", "ingles"]

# Valores válidos para cada campo
COMPONENTES_VALIDOS = {"matematicas", "lectura", "sociales", "naturales", "ingles"}


class Simulacro(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre del Simulacro")
    soluciones_s1 = models.CharField(max_length=150, verbose_name="Soluciones Sesión 1 (120 ítems)")
    soluciones_s2 = models.CharField(max_length=150, verbose_name="Soluciones Sesión 2 (134 ítems)")
    puntos_corte_s1 = models.JSONField(verbose_name="Puntos de Corte Sesión 1", default=dict)
    puntos_corte_s2 = models.JSONField(verbose_name="Puntos de Corte Sesión 2", default=dict)
    umbral = models.IntegerField(
        default=200, 
        verbose_name="Umbral de Puntaje Mínimo", 
        help_text="Puntaje global mínimo aceptable. Los puntajes menores se ajustarán dinámicamente."
    )
    umbral_1 = models.IntegerField(
        default=140,
        verbose_name="Umbral 1",
        help_text="Puntaje global real para el primer rango (inclusive)."
    )
    objetivo_1 = models.IntegerField(
        default=245,
        verbose_name="Objetivo Base 1",
        help_text="Objetivo base asignado si el puntaje global es menor o igual a Umbral 1."
    )
    umbral_2 = models.IntegerField(
        default=240,
        verbose_name="Umbral 2",
        help_text="Puntaje global real para el segundo rango (inclusive)."
    )
    objetivo_2 = models.IntegerField(
        default=280,
        verbose_name="Objetivo Base 2",
        help_text="Objetivo base asignado si el puntaje global está entre Umbral 1 + 1 y Umbral 2."
    )
    objetivo_3 = models.IntegerField(
        default=310,
        verbose_name="Objetivo Base 3",
        help_text="Objetivo base asignado si el puntaje global es mayor que Umbral 2."
    )
    boost_min = models.IntegerField(
        default=6,
        verbose_name="Boost Mínimo",
        help_text="Incremento aleatorio mínimo para sumar al objetivo base."
    )
    boost_max = models.IntegerField(
        default=12,
        verbose_name="Boost Máximo",
        help_text="Incremento aleatorio máximo para sumar al objetivo base."
    )

    componentes_s1 = models.JSONField(
        verbose_name="Orden de componentes Sesión 1",
        default=list,
        help_text=(
            'Lista ordenada de componentes para S1. Ejemplo: '
            '["matematicas", "lectura", "sociales", "naturales"]. '
            f'Valores válidos: {sorted(COMPONENTES_VALIDOS)}.'
        ),
    )
    componentes_s2 = models.JSONField(
        verbose_name="Orden de componentes Sesión 2",
        default=list,
        help_text=(
            'Lista ordenada de componentes para S2. Ejemplo: '
            '["sociales", "matematicas", "naturales", "ingles"]. '
            f'Valores válidos: {sorted(COMPONENTES_VALIDOS)}.'
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Simulacro"
        verbose_name_plural = "Simulacros"

    def __str__(self):
        return self.nombre

    def get_componentes_s1(self) -> list:
        """Retorna el orden de componentes S1, usando el default si está vacío."""
        return self.componentes_s1 if self.componentes_s1 else _DEFAULT_COMPONENTES_S1

    def get_componentes_s2(self) -> list:
        """Retorna el orden de componentes S2, usando el default si está vacío."""
        return self.componentes_s2 if self.componentes_s2 else _DEFAULT_COMPONENTES_S2


class ResultadoSimulacro(models.Model):
    alumno = models.ForeignKey(
        'academico.Alumno', 
        on_delete=models.CASCADE, 
        related_name="resultados_simulacros",
        verbose_name="Alumno"
    )
    simulacro = models.ForeignKey(
        Simulacro, 
        on_delete=models.CASCADE, 
        related_name="resultados",
        verbose_name="Simulacro"
    )
    respuestas_s1 = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Respuestas extraídas S1"
    )
    respuestas_s2 = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Respuestas extraídas S2"
    )
    puntaje_global = models.FloatField(default=0.0, verbose_name="Puntaje Global")
    puntaje_matematicas = models.FloatField(default=0.0, verbose_name="Matemáticas")
    puntaje_lectura = models.FloatField(default=0.0, verbose_name="Lectura Crítica")
    puntaje_sociales = models.FloatField(default=0.0, verbose_name="Sociales y Ciudadanas")
    puntaje_naturales = models.FloatField(default=0.0, verbose_name="Ciencias Naturales")
    puntaje_ingles = models.FloatField(default=0.0, verbose_name="Inglés")
    
    puntaje_global_modificado = models.FloatField(default=0.0, verbose_name="Puntaje Global Modificado")
    puntaje_matematicas_modificado = models.FloatField(default=0.0, verbose_name="Matemáticas Modificado")
    puntaje_lectura_modificado = models.FloatField(default=0.0, verbose_name="Lectura Crítica Modificado")
    puntaje_sociales_modificado = models.FloatField(default=0.0, verbose_name="Sociales y Ciudadanas Modificado")
    puntaje_naturales_modificado = models.FloatField(default=0.0, verbose_name="Ciencias Naturales Modificado")
    puntaje_ingles_modificado = models.FloatField(default=0.0, verbose_name="Inglés Modificado")

    fecha_realizacion = models.DateField(verbose_name="Fecha de realización", null=True, blank=True)
    registrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="simulacros_registrados",
        verbose_name="Registrador"
    )
    fecha_calificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resultado de Simulacro"
        verbose_name_plural = "Resultados de Simulacros"
        unique_together = ('alumno', 'simulacro')

    def __str__(self):
        return f"{self.alumno} - {self.simulacro}"

    @property
    def estado(self):
        # Si tiene almacenada la data de ambas sesiones, se considera calificado.
        # Caso contrario está incompleto.
        if self.respuestas_s1 and self.respuestas_s2:
            return "Calificado"
        return "Incompleto"


# ================================================================
# SIMULACRO DIAGNÓSTICO (1 sola sesión, 90 preguntas, 3 columnas)
# ================================================================
_DEFAULT_COMPONENTES_SD = ["matematicas", "lectura", "sociales", "naturales", "ingles"]


class SimulacroDiagnostico(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre del Simulacro Diagnóstico")
    soluciones = models.CharField(max_length=150, verbose_name="Soluciones (90 ítems)")
    puntos_corte = models.JSONField(
        verbose_name="Puntos de Corte", 
        default=dict,
        blank=True,
        help_text='Ejemplo: {"cortes": [18, 36, 54, 72]}'
    )
    umbral = models.IntegerField(
        default=200, 
        verbose_name="Umbral de Puntaje Mínimo", 
        help_text="Puntaje global mínimo aceptable."
    )
    umbral_1 = models.IntegerField(default=140, verbose_name="Umbral 1")
    objetivo_1 = models.IntegerField(default=245, verbose_name="Objetivo Base 1")
    umbral_2 = models.IntegerField(default=240, verbose_name="Umbral 2")
    objetivo_2 = models.IntegerField(default=280, verbose_name="Objetivo Base 2")
    objetivo_3 = models.IntegerField(default=310, verbose_name="Objetivo Base 3")
    boost_min = models.IntegerField(default=6, verbose_name="Boost Mínimo")
    boost_max = models.IntegerField(default=12, verbose_name="Boost Máximo")

    componentes = models.JSONField(
        verbose_name="Orden de componentes",
        default=list,
        blank=True,
        help_text=(
            'Lista ordenada de componentes. Ejemplo: '
            '["matematicas", "lectura", "sociales", "naturales", "ingles"].'
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Simulacro Diagnóstico"
        verbose_name_plural = "Simulacros Diagnósticos"

    def clean(self):
        super().clean()
        if self.soluciones:
            sol_limpia = self.soluciones.replace(' ', '').replace('\r', '').replace('\n', '').strip()
            if len(sol_limpia) != 90:
                raise ValidationError({
                    'soluciones': f'La cadena de soluciones para el Simulacro Diagnóstico debe tener EXACTAMENTE 90 caracteres. Actualmente tiene {len(sol_limpia)}.'
                })

    def save(self, *args, **kwargs):
        if self.soluciones:
            self.soluciones = self.soluciones.replace(' ', '').replace('\r', '').replace('\n', '').strip()
        super().save(*args, **kwargs)

    def get_componentes(self) -> list:
        return self.componentes if self.componentes else _DEFAULT_COMPONENTES_SD


class ResultadoSimulacroDiagnostico(models.Model):
    alumno = models.ForeignKey(
        'academico.Alumno', 
        on_delete=models.CASCADE, 
        related_name="resultados_simulacros_diagnosticos",
        verbose_name="Alumno"
    )
    simulacro = models.ForeignKey(
        SimulacroDiagnostico, 
        on_delete=models.CASCADE, 
        related_name="resultados",
        verbose_name="Simulacro Diagnóstico"
    )
    respuestas = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Respuestas extraídas (90 ítems)"
    )
    puntaje_global = models.FloatField(default=0.0, verbose_name="Puntaje Global")
    puntaje_matematicas = models.FloatField(default=0.0, verbose_name="Matemáticas")
    puntaje_lectura = models.FloatField(default=0.0, verbose_name="Lectura Crítica")
    puntaje_sociales = models.FloatField(default=0.0, verbose_name="Sociales y Ciudadanas")
    puntaje_naturales = models.FloatField(default=0.0, verbose_name="Ciencias Naturales")
    puntaje_ingles = models.FloatField(default=0.0, verbose_name="Inglés")
    
    puntaje_global_modificado = models.FloatField(default=0.0, verbose_name="Puntaje Global Modificado")
    puntaje_matematicas_modificado = models.FloatField(default=0.0, verbose_name="Matemáticas Modificado")
    puntaje_lectura_modificado = models.FloatField(default=0.0, verbose_name="Lectura Crítica Modificado")
    puntaje_sociales_modificado = models.FloatField(default=0.0, verbose_name="Sociales y Ciudadanas Modificado")
    puntaje_naturales_modificado = models.FloatField(default=0.0, verbose_name="Ciencias Naturales Modificado")
    puntaje_ingles_modificado = models.FloatField(default=0.0, verbose_name="Inglés Modificado")

    fecha_realizacion = models.DateField(verbose_name="Fecha de realización", null=True, blank=True)
    registrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="simulacros_diagnosticos_registrados",
        verbose_name="Registrador"
    )
    fecha_calificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resultado de Simulacro Diagnóstico"
        verbose_name_plural = "Resultados de Simulacros Diagnósticos"
        unique_together = ('alumno', 'simulacro')

    def __str__(self):
        return f"{self.alumno} - {self.simulacro}"

    @property
    def estado(self):
        if self.respuestas and len(self.respuestas) >= 90:
            return "Calificado"
        return "Incompleto"
