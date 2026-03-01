from django.db import models
from django.conf import settings
from curriculo.models import Modulo, Materia
from .banco import Pregunta, Opcion

class Simulacro(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.SET_NULL, null=True, blank=True, related_name='simulacros')
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='simulacros_creados')
    titulo = models.CharField(max_length=255)
    
    # "Pico y cédula"
    fecha_apertura = models.DateTimeField(help_text="Cuándo se puede empezar a tomar")
    fecha_cierre = models.DateTimeField(help_text="Cuándo se cierra definitivamente")
    
    # Límite de tiempo
    duracion_minutos = models.PositiveIntegerField(help_text="Tiempo máximo para completarlo (Pasa al frontend para el cronómetro)")
    orden = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.titulo

class SesionSimulacro(models.Model):
    simulacro = models.ForeignKey(Simulacro, on_delete=models.CASCADE, related_name='sesiones')
    nombre = models.CharField(max_length=100, help_text="Ej: Sesión 1 - Mañana")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        
    def __str__(self):
        return f"{self.simulacro.titulo} - {self.nombre}"

class ComponenteSesion(models.Model):
    sesion = models.ForeignKey(SesionSimulacro, on_delete=models.CASCADE, related_name='componentes')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['orden']
        
    def __str__(self):
        return f"{self.sesion.simulacro.titulo} - {self.sesion.nombre} - {self.materia.nombre}"

class PreguntaSimulacro(models.Model):
    componente = models.ForeignKey(ComponenteSesion, on_delete=models.CASCADE, related_name='preguntas_componente')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

class IntentoSimulacro(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='intentos_simulacro')
    simulacro = models.ForeignKey(Simulacro, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    
    # Puntaje ponderado ICFES (0 - 500)
    puntaje_global = models.PositiveIntegerField(blank=True, null=True)
    resultados_detallados = models.JSONField(blank=True, null=True, help_text="Puntajes calculados desglosados (por componentes)")

    def __str__(self):
        return f"Intento Simulacro {self.id} - {self.usuario}"

class IntentoSesion(models.Model):
    intento_simulacro = models.ForeignKey(IntentoSimulacro, on_delete=models.CASCADE, related_name='intentos_sesion')
    sesion = models.ForeignKey(SesionSimulacro, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)

class RespuestaSimulacro(models.Model):
    intento_sesion = models.ForeignKey(IntentoSesion, on_delete=models.CASCADE, related_name='respuestas')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL, null=True, blank=True)
    es_correcta = models.BooleanField(default=False)
