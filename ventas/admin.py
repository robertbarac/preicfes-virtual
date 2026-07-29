from django.contrib import admin
from .models import Vendedor, PreVenta, Incidencia, IncidenciaImagen

class IncidenciaInline(admin.TabularInline):
    model = Incidencia
    extra = 1
    fields = ['etapa', 'user', 'texto', 'fecha']
    readonly_fields = ['fecha']

class IncidenciaImagenInline(admin.TabularInline):
    model = IncidenciaImagen
    extra = 1

@admin.register(PreVenta)
class PreVentaAdmin(admin.ModelAdmin):
    list_display = ['nombre_estudiante', 'nombre_padre_madre', 'telefono', 'user', 'fecha_creacion']
    list_filter = ['user', 'fecha_creacion']
    search_fields = ['nombre_estudiante', 'nombre_padre_madre', 'telefono']
    inlines = [IncidenciaInline]

@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ['preventa', 'etapa', 'user', 'fecha', 'fecha_creacion']
    list_filter = ['etapa', 'fecha', 'user']
    search_fields = ['preventa__nombre_estudiante', 'texto']
    inlines = [IncidenciaImagenInline]

@admin.register(IncidenciaImagen)
class IncidenciaImagenAdmin(admin.ModelAdmin):
    list_display = ['incidencia', 'imagen', 'fecha_creacion']

# Keep old model
admin.site.register(Vendedor)
