# ubicaciones/admin.py
from django.contrib import admin
from .models import Departamento, Municipio, Sede, Salon, Colegio

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'departamento')
    search_fields = ('nombre',)
    list_filter = ('departamento',)

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'municipio')
    search_fields = ('nombre',)
    list_filter = ('municipio__departamento', 'municipio',)
    
    def departamento(self, obj):
        return obj.municipio.departamento
    departamento.admin_order_fied = 'municipio__departamento'
    departamento.short_description = 'Departamento'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser:
            queryset = queryset.filter(municipio=request.user.municipio)
        return queryset

@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('numero', 'sede', 'municipio', 'capacidad_sillas')  
    search_fields = ('numero',)
    list_filter = ('sede__municipio', 'sede',)  # Filtrar por Municipio y Sede

    def municipio(self, obj):
        return obj.sede.municipio  # Mostrar municipio en la lista de salones
    municipio.admin_order_field = 'sede__municipio'  # Permite ordenar por municipio
    municipio.short_description = 'Municipio'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user

        if user.is_superuser:
            return queryset
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                return queryset.filter(sede__municipio__departamento=user.departamento)
            return queryset.none() # Si no tiene departamento, no ve nada
        else:
            return queryset.filter(sede__municipio=user.municipio)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'sede':
            user = request.user
            if not user.is_superuser:
                if user.groups.filter(name='CoordinadorDepartamental').exists():
                    if user.departamento:
                        kwargs["queryset"] = Sede.objects.filter(municipio__departamento=user.departamento)
                else:
                    kwargs["queryset"] = Sede.objects.filter(municipio=user.municipio)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Colegio)
class ColegioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'municipio', 'departamento')
    search_fields = ('nombre', 'municipio__nombre', 'municipio__departamento__nombre')
    list_filter = ('municipio__departamento', 'municipio')

    def departamento(self, obj):
        return obj.municipio.departamento
    departamento.admin_order_field = 'municipio__departamento'
    departamento.short_description = 'Departamento'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        if user.is_superuser:
            return queryset
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                return queryset.filter(municipio__departamento=user.departamento)
            return queryset.none()
        return queryset.filter(municipio=user.municipio)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'municipio':
            user = request.user
            if not user.is_superuser:
                if user.groups.filter(name='CoordinadorDepartamental').exists():
                    if user.departamento:
                        kwargs['queryset'] = Municipio.objects.filter(departamento=user.departamento)
                else:
                    kwargs['queryset'] = Municipio.objects.filter(id=user.municipio_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
