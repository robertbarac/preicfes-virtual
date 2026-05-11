from django.contrib import admin
from .models.banco import Pregunta, Opcion, ImagenPregunta
from .models.talleres import Taller, PreguntaTaller
from .models.simulacros import (
    Simulacro, VentanaSimulacro, SesionSimulacro, Componente, 
    ComponenteSesion, PreguntaSimulacro, IntentoSimulacro, 
    IntentoSesion, RespuestaSimulacro
)

# --- BANCO DE PREGUNTAS ---

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 4

class ImagenPreguntaInline(admin.TabularInline):
    model = ImagenPregunta
    extra = 1

@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ('id', 'tema_nombre', 'enunciado_corto', 'fecha_creacion')
    list_filter = ('tema__materia', 'tema')
    search_fields = ('enunciado', 'tema__nombre', 'id')
    inlines = [ImagenPreguntaInline, OpcionInline]

    def enunciado_corto(self, obj):
        return obj.enunciado[:75] + '...' if len(obj.enunciado) > 75 else obj.enunciado
    enunciado_corto.short_description = 'Enunciado'

    def tema_nombre(self, obj):
        return obj.tema.nombre if obj.tema else 'General'
    tema_nombre.short_description = 'Tema'

# --- TALLERES ---

class PreguntaTallerInline(admin.TabularInline):
    model = PreguntaTaller
    extra = 1
    autocomplete_fields = ['pregunta']

@admin.register(Taller)
class TallerAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'modulo', 'tema', 'orden', 'intentos_permitidos')
    list_filter = ('modulo', 'tema')
    search_fields = ('titulo', 'descripcion')
    inlines = [PreguntaTallerInline]

# --- SIMULACROS ---

class SesionSimulacroInline(admin.TabularInline):
    model = SesionSimulacro
    extra = 2

@admin.register(Simulacro)
class SimulacroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'modulo', 'estado', 'duracion_minutos')
    list_filter = ('modulo', 'estado')
    search_fields = ('titulo', )
    inlines = [SesionSimulacroInline]

@admin.register(VentanaSimulacro)
class VentanaSimulacroAdmin(admin.ModelAdmin):
    list_display = ('simulacro', 'fecha_apertura', 'fecha_cierre', 'is_active')
    list_filter = ('simulacro', 'fecha_apertura')

@admin.register(Componente)
class ComponenteAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

class ComponenteSesionInline(admin.TabularInline):
    model = ComponenteSesion
    extra = 1

@admin.register(SesionSimulacro)
class SesionSimulacroAdmin(admin.ModelAdmin):
    list_display = ('simulacro', 'nombre', 'orden')
    list_filter = ('simulacro',)
    inlines = [ComponenteSesionInline]

class PreguntaSimulacroInline(admin.TabularInline):
    model = PreguntaSimulacro
    extra = 3
    autocomplete_fields = ['pregunta']

@admin.register(ComponenteSesion)
class ComponenteSesionAdmin(admin.ModelAdmin):
    list_display = ('sesion', 'componente', 'orden')
    list_filter = ('sesion__simulacro', 'componente')
    search_fields = ('componente__nombre',)
    inlines = [PreguntaSimulacroInline]

# --- INTENTOS DE SIMULACRO ---

class IntentoSesionInline(admin.TabularInline):
    model = IntentoSesion
    extra = 0
    readonly_fields = ('fecha_inicio', 'fecha_fin', 'get_tiempo_empleado_minutos')

@admin.register(IntentoSimulacro)
class IntentoSimulacroAdmin(admin.ModelAdmin):
    list_display = ('simulacro', 'usuario', 'fecha_inicio', 'fecha_fin', 'puntaje_global')
    list_filter = ('simulacro',)
    search_fields = ('usuario__username', 'usuario__email', 'simulacro__titulo')
    inlines = [IntentoSesionInline]
    readonly_fields = ('fecha_inicio', 'fecha_fin', 'tiempo_empleado_minutos', 'puntaje_global', 'resultados_detallados')

@admin.register(RespuestaSimulacro)
class RespuestaSimulacroAdmin(admin.ModelAdmin):
    list_display = ('intento_sesion', 'pregunta', 'opcion_seleccionada', 'es_correcta')
    list_filter = ('es_correcta',)
    search_fields = ('intento_sesion__intento_simulacro__usuario__username',)
    readonly_fields = ('intento_sesion', 'pregunta', 'opcion_seleccionada', 'es_correcta')
