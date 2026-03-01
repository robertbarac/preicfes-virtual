from django.contrib import admin
from .models.banco import Pregunta, Opcion, ImagenPregunta
from .models.talleres import Taller, PreguntaTaller
from .models.simulacros import Simulacro, SesionSimulacro, ComponenteSesion

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
    list_display = ('titulo', 'modulo', 'fecha_apertura', 'fecha_cierre', 'duracion_minutos')
    list_filter = ('modulo', )
    search_fields = ('titulo', )
    inlines = [SesionSimulacroInline]
