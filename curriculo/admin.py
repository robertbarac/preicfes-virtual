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
    search_fields = ('nombre', )
    ordering = ('orden', )

