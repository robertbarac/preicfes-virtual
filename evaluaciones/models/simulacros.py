from django.db import models
from django.conf import settings
from django.utils import timezone
from curriculo.models import Modulo, Materia
from .banco import Pregunta, Opcion


# ─── Constantes de ponderación ICFES ─────────────────────────────────────────
ICFES_PESO_DEFAULT = 3   # Matemáticas, Ciencias, Lectura Crítica, Sociales
ICFES_PESO_INGLES  = 1   # Inglés vale menos


def calcular_puntaje_global(resultados_por_componente):
    """
    Calcula el puntaje ICFES ponderado (0-500).

    resultados_por_componente: lista de dicts con claves:
      - materia_nombre (str)
      - correctas (int)
      - total (int)

    Todos los componentes pesan 3 excepto Inglés que pesa 1.
    Fórmula: media ponderada de porcentajes × 5, redondeado.
    """
    suma_ponderada = 0.0
    suma_pesos = 0
    for comp in resultados_por_componente:
        if not comp.get("total"):
            continue
        nombre = (comp.get("materia_nombre") or "").lower()
        peso = ICFES_PESO_INGLES if ("ingles" in nombre or "inglés" in nombre) else ICFES_PESO_DEFAULT
        pct = (comp["correctas"] / comp["total"]) * 100
        suma_ponderada += pct * peso
        suma_pesos += peso
    if suma_pesos == 0:
        return 0
    media = suma_ponderada / suma_pesos
    return round(media * 5)   # 0 – 500


# ─── Simulacro ────────────────────────────────────────────────────────────────

class Simulacro(models.Model):
    ESTADOS = (
        ("borrador", "Borrador"),
        ("publicado", "Publicado"),
    )

    modulo   = models.ForeignKey(Modulo, on_delete=models.SET_NULL, null=True, blank=True, related_name="simulacros")
    creador  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="simulacros_creados")
    titulo   = models.CharField(max_length=255)
    estado   = models.CharField(max_length=20, choices=ESTADOS, default="borrador")

    # Duración de cada sesión (el cronómetro va por sesión)
    duracion_minutos = models.PositiveIntegerField(
        help_text="Tiempo máximo por sesión en minutos (se pasa al cronómetro del frontend)."
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return self.titulo

    def ventana_activa(self):
        """Retorna la VentanaSimulacro activa en este momento, o None."""
        ahora = timezone.now()
        return self.ventanas.filter(
            fecha_apertura__lte=ahora,
            fecha_cierre__gte=ahora
        ).first()

    def esta_disponible(self):
        """True si publicado y tiene ventana activa ahora."""
        return self.estado == "publicado" and self.ventana_activa() is not None


# ─── Ventana de tiempo ────────────────────────────────────────────────────────

class VentanaSimulacro(models.Model):
    """
    Período durante el cual el simulacro puede realizarse.
    Un simulacro puede tener múltiples ventanas (p. ej. en fechas distintas).
    Los estudiantes solo ven el simulacro cuando hay una ventana activa.
    """
    simulacro      = models.ForeignKey(Simulacro, on_delete=models.CASCADE, related_name="ventanas")
    creador        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ventanas_simulacro_creadas")
    fecha_apertura = models.DateTimeField(help_text="Cuándo se abre el simulacro para los estudiantes.")
    fecha_cierre   = models.DateTimeField(help_text="Cuándo se cierra definitivamente.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_apertura"]

    def is_active(self):
        ahora = timezone.now()
        return self.fecha_apertura <= ahora <= self.fecha_cierre

    def __str__(self):
        estado = "ACTIVA" if self.is_active() else "CERRADA"
        return (
            f"Ventana {self.id} ({self.simulacro.titulo}) — "
            f"{self.fecha_apertura.strftime('%Y-%m-%d %H:%M')} → "
            f"{self.fecha_cierre.strftime('%Y-%m-%d %H:%M')} [{estado}]"
        )


# ─── Estructura del simulacro ─────────────────────────────────────────────────

class SesionSimulacro(models.Model):
    simulacro = models.ForeignKey(Simulacro, on_delete=models.CASCADE, related_name="sesiones")
    nombre    = models.CharField(max_length=100, help_text="Ej: Sesión 1 — Mañana")
    orden     = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"{self.simulacro.titulo} — {self.nombre}"


class Componente(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Matemáticas, Ciencias Naturales, Lectura Crítica")

    def __str__(self):
        return self.nombre


class ComponenteSesion(models.Model):
    sesion     = models.ForeignKey(SesionSimulacro, on_delete=models.CASCADE, related_name="componentes")
    componente = models.ForeignKey(Componente, on_delete=models.CASCADE)
    orden      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"{self.sesion} — {self.componente.nombre}"


class PreguntaSimulacro(models.Model):
    """Relaciona una Pregunta del banco con un ComponenteSesion."""
    componente = models.ForeignKey(ComponenteSesion, on_delete=models.CASCADE, related_name="preguntas_componente")
    pregunta   = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    orden      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"PregSim {self.id} — {self.componente}"


# ─── Intento del estudiante ───────────────────────────────────────────────────

class IntentoSimulacro(models.Model):
    usuario   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="intentos_simulacro")
    simulacro = models.ForeignKey(Simulacro, on_delete=models.CASCADE, related_name="intentos")
    ventana   = models.ForeignKey(
        VentanaSimulacro, on_delete=models.SET_NULL, null=True, blank=True, related_name="intentos"
    )

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin    = models.DateTimeField(blank=True, null=True)

    # Tiempo real empleado en minutos (calculado al finalizar todo el simulacro)
    tiempo_empleado_minutos = models.PositiveIntegerField(blank=True, null=True)

    # Puntaje ponderado ICFES (0–500)
    puntaje_global        = models.PositiveIntegerField(blank=True, null=True)
    resultados_detallados = models.JSONField(
        blank=True, null=True,
        help_text="Lista: [{materia_nombre, correctas, total, porcentaje, peso}]"
    )

    class Meta:
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(fields=['usuario', 'simulacro']),
            models.Index(fields=['fecha_fin']),
        ]

    def __str__(self):
        return f"Intento #{self.id} — {self.usuario} en {self.simulacro}"


class IntentoSesion(models.Model):
    """
    Registra el tiempo y las respuestas de una sesión específica dentro
    de un IntentoSimulacro. Cada sesión se hace al completo.
    """
    intento_simulacro = models.ForeignKey(IntentoSimulacro, on_delete=models.CASCADE, related_name="intentos_sesion")
    sesion            = models.ForeignKey(SesionSimulacro, on_delete=models.CASCADE, related_name="intentos_sesion")
    fecha_inicio      = models.DateTimeField(auto_now_add=True)
    fecha_fin         = models.DateTimeField(blank=True, null=True)

    def get_tiempo_empleado_minutos(self):
        if self.fecha_fin:
            delta = self.fecha_fin - self.fecha_inicio
            return round(delta.total_seconds() / 60, 1)
        return None

    def __str__(self):
        return f"IntentoSesion #{self.id} — {self.sesion.nombre}"


class RespuestaSimulacro(models.Model):
    intento_sesion      = models.ForeignKey(IntentoSesion, on_delete=models.CASCADE, related_name="respuestas")
    pregunta            = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL, null=True, blank=True)
    es_correcta         = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['intento_sesion']),
        ]

    def __str__(self):
        return f"Resp P{self.pregunta_id} en IS{self.intento_sesion_id}"
