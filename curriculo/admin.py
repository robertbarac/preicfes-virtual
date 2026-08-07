from django.contrib import admin
from .models.core import Programa, Ciclo, Materia, Tema, Modulo, ClaseVirtual, Asistencia


@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'tipo', 'slug', 'activo')
    list_filter   = ('tipo', 'activo')
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Ciclo)
class CicloAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'programa', 'orden', 'visible')
    list_filter   = ('programa', 'visible')
    ordering      = ('programa', 'orden')


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display  = ('nombre',)
    search_fields = ('nombre',)
    filter_horizontal = ('programas',)


@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'materia')
    list_filter   = ('materia',)
    search_fields = ('nombre', 'materia__nombre')


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'ciclo', 'orden', 'activo')
    list_filter   = ('ciclo__programa', 'ciclo', 'activo')
    search_fields = ('nombre', 'ciclo__nombre', 'ciclo__programa__nombre')
    ordering      = ('ciclo__programa', 'ciclo__orden', 'orden')


@admin.register(ClaseVirtual)
class ClaseVirtualAdmin(admin.ModelAdmin):
    list_display  = ('titulo', 'modulo', 'fecha', 'hora_inicio', 'hora_fin')
    list_filter   = ('modulo__ciclo__programa', 'modulo', 'fecha')
    search_fields = ('titulo',)


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display  = ('alumno', 'clase', 'asistio', 'fecha_registro')
    list_filter   = ('asistio', 'clase__fecha', 'clase')
    search_fields = ('alumno__username', 'alumno__first_name',
                     'alumno__last_name', 'clase__titulo')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('alumno', 'clase', 'fecha_registro')
        return self.readonly_fields
