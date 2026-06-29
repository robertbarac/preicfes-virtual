from django.contrib import admin
from .models import Post, BloqueContenido


class BloqueContenidoInline(admin.StackedInline):
    model = BloqueContenido
    extra = 0
    fields = ('tipo', 'orden', 'contenido_texto', 'archivo_imagen', 'url')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'modulo', 'tema', 'estado', 'orden', 'creador', 'fecha_creacion')
    list_filter = ('estado', 'modulo', 'tema__materia')
    search_fields = ('titulo',)
    ordering = ('modulo', 'orden')
    inlines = [BloqueContenidoInline]


@admin.register(BloqueContenido)
class BloqueContenidoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tipo', 'orden', 'post')
    list_filter = ('tipo',)
    search_fields = ('post__titulo',)
