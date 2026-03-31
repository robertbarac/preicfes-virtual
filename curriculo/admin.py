from django.contrib import admin
from .models.core import Materia, Tema, Modulo

@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre', )

@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'materia')
    list_filter = ('materia', )
    search_fields = ('nombre', 'materia__nombre')

@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'orden')
    list_filter = ('activo', )
from .models.core import ClaseVirtual, Asistencia

@admin.register(ClaseVirtual)
class ClaseVirtualAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'modulo', 'fecha', 'hora_inicio', 'hora_fin')
    list_filter = ('modulo', 'fecha')
    search_fields = ('titulo', )

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'clase', 'asistio', 'fecha_registro')
    list_filter = ('asistio', 'clase__fecha', 'clase')
    search_fields = ('alumno__username', 'alumno__first_name', 'alumno__last_name', 'clase__titulo')
    
    def get_readonly_fields(self, request, obj=None):
        if obj: # editing an existing object
            return ('alumno', 'clase', 'fecha_registro')
        return self.readonly_fields
