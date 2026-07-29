from django.contrib import admin
from .models import AcuerdoPago, Cuota, Deuda, Egreso, HistorialModificacion, Recibo, MetaRecaudo, TarifaClase
from ubicaciones.models import Sede
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum

from datetime import datetime

Usuario = get_user_model()  # Obtener dinámicamente el modelo de usuario


class FechaCulminacionRangeFilter(admin.SimpleListFilter):
    title = 'Fecha Culminación Alumno'
    parameter_name = 'culminacion_desde'
    parameter_name_desde = 'culminacion_desde'
    parameter_name_hasta = 'culminacion_hasta'
    template = 'admin/date_range_filter.html'

    def __init__(self, request, params, model, model_admin):
        self.request_get = request.GET
        if self.parameter_name_desde in params:
            self.value_desde = params.pop(self.parameter_name_desde)[-1]
        else:
            self.value_desde = None

        if self.parameter_name_hasta in params:
            self.value_hasta = params.pop(self.parameter_name_hasta)[-1]
        else:
            self.value_hasta = None

        super().__init__(request, params, model, model_admin)

    def expected_parameters(self):
        return [self.parameter_name_desde, self.parameter_name_hasta]

    def lookups(self, request, model_admin):
        return (('custom', 'Personalizado'),)

    def queryset(self, request, queryset):
        desde = self.value_desde or request.GET.get(self.parameter_name_desde)
        hasta = self.value_hasta or request.GET.get(self.parameter_name_hasta)

        if desde:
            try:
                fecha_desde = datetime.strptime(desde, '%Y-%m-%d').date()
                queryset = queryset.filter(deuda__alumno__fecha_culminacion__gte=fecha_desde)
            except ValueError:
                pass

        if hasta:
            try:
                fecha_hasta = datetime.strptime(hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(deuda__alumno__fecha_culminacion__lte=fecha_hasta)
            except ValueError:
                pass

        return queryset

    def choices(self, changelist):
        return []

    def get_preserved_params(self):
        params = []
        for key, value_list in self.request_get.lists():
            if key not in (self.parameter_name_desde, self.parameter_name_hasta, 'page', 'p'):
                for val in value_list:
                    params.append((key, val))
        return params

    @property
    def current_value_desde(self):
        return self.value_desde or self.request_get.get(self.parameter_name_desde, '')

    @property
    def current_value_hasta(self):
        return self.value_hasta or self.request_get.get(self.parameter_name_hasta, '')

    @property
    def reset_url(self):
        cleaned_get = self.request_get.copy()
        if self.parameter_name_desde in cleaned_get:
            del cleaned_get[self.parameter_name_desde]
        if self.parameter_name_hasta in cleaned_get:
            del cleaned_get[self.parameter_name_hasta]
        if 'p' in cleaned_get:
            del cleaned_get['p']
        encoded = cleaned_get.urlencode()
        return f'?{encoded}' if encoded else '?'


@admin.register(AcuerdoPago)
class AcuerdoPagoAdmin(admin.ModelAdmin):
    list_display = ('cuota', 'fecha_prometida_pago', 'estado')
    list_filter = ('estado', 'fecha_prometida_pago', 'cuota__fecha_pago', 'cuota__deuda__alumno__grupo_actual__salon__sede__municipio')
    search_fields = ('cuota__deuda__alumno__nombres', 'cuota__deuda__alumno__primer_apellido', 'cuota__deuda__alumno__municipio__nombre')
    date_hierarchy = 'fecha_prometida_pago'
    list_editable = ('estado',)

@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ('deuda', 'monto', 'monto_abonado', 'fecha_vencimiento', 'fecha_pago', 'estado', 'metodo_pago', 'editado_por', 'fecha_edicion', 'get_tipo_programa', 'get_departamento')
    list_filter = ('estado', 'deuda__alumno__estado', FechaCulminacionRangeFilter, 'editado_por', 'deuda__alumno__tipo_programa', 'deuda__alumno__municipio__departamento', 'deuda__alumno__municipio', 'deuda__alumno__grupo_actual__salon__sede', 'fecha_vencimiento', 'fecha_pago')
    search_fields = ('deuda__alumno__nombres', 'deuda__alumno__primer_apellido', 'deuda__alumno__municipio__nombre', 'editado_por')
    date_hierarchy = 'fecha_vencimiento'
    list_editable = ('monto_abonado', 'estado', 'metodo_pago')

    def changelist_view(self, request, extra_context=None):
        from django.db.models import Sum
        from cartera.models import Deuda

        # Obtener el queryset original con los filtros aplicados por el admin
        changelist = self.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        # Filtrar solo cuotas de alumnos activos
        active_queryset = queryset.filter(deuda__alumno__estado='activo')

        # 1) Total de deudas (como en el informe diario)
        total_deudas = Deuda.objects.filter(
            alumno__estado='activo'
        ).aggregate(total_valor=Sum('valor_total'))
        total_valor = total_deudas.get('total_valor') or 0
        total_valor_str = f"{total_valor:,.0f}"

        # 2) Total de cuotas según estado:
        #    - emitida, vencida, pagada_parcial → sumar 'monto'
        #    - pagada → sumar 'monto_abonado'

        emitidas_y_vencidas = active_queryset.filter(estado__in=['emitida', 'vencida'])
        pagadas_y_parciales = active_queryset.filter(estado__in=['pagada_parcial', 'pagada'])

        total_emitidas_vencidas = emitidas_y_vencidas.aggregate(s=Sum('monto'))['s'] or 0
        total_pagadas_y_parciales = pagadas_y_parciales.aggregate(s=Sum('monto_abonado'))['s'] or 0

        total_cuotas = total_emitidas_vencidas + total_pagadas_y_parciales
        total_monto_str = f"{total_cuotas:,.0f}"

        # Preparar el contexto extra
        extra_context = extra_context or {}
        extra_context['total_valor_deudas'] = total_valor_str
        extra_context['total_monto_cuotas'] = total_monto_str

        # Llamar al método original con el contexto extra
        response = super().changelist_view(request, extra_context=extra_context)

        # Modificar el título después de que la respuesta se ha generado
        from django.http import HttpResponseRedirect
        if not isinstance(response, HttpResponseRedirect) and hasattr(response, 'context_data') \
           and response.context_data and 'title' in response.context_data:
            response.context_data['title'] = (
                f"Seleccionar cuota para modificar "
                f"(Valor Deudas: ${total_valor_str} | Montos Cuotas: ${total_monto_str})"
            )

        return response  

    fieldsets = (
        ('Información Básica', {
            'fields': ('deuda', 'monto', 'monto_abonado', 'fecha_vencimiento')
        }),
        ('Estado y Método de Pago', {
            'fields': ('estado', 'metodo_pago')
        }),
        ('Auditoría', {
            'fields': ('editado_por', 'fecha_edicion'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('editado_por', 'fecha_edicion')

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'deuda__alumno',
            'deuda__alumno__municipio__departamento'
        )
        # Si NO es superuser, filtrar por municipio
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede__municipio=request.user.municipio)
        return queryset

    def get_form(self, request, obj=None, **kwargs):
        """Filtra las deudas según el municipio del usuario logueado (excepto superusuarios)."""
        form = super().get_form(request, obj, **kwargs)
        # Si NO es superuser, filtrar por municipio
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            form.base_fields['deuda'].queryset = Deuda.objects.filter(
                alumno__grupo_actual__salon__sede__municipio=request.user.municipio
            )
        return form

    def get_tipo_programa(self, obj):
        return obj.deuda.alumno.get_tipo_programa_display()
    get_tipo_programa.short_description = 'Tipo de Programa'
    get_tipo_programa.admin_order_field = 'deuda__alumno__tipo_programa'

    def get_departamento(self, obj):
        if obj.deuda.alumno.municipio:
            return obj.deuda.alumno.municipio.departamento.nombre
        return 'N/A'
    get_departamento.short_description = 'Departamento'
    get_departamento.admin_order_field = 'deuda__alumno__municipio__departamento'
    
    def get_estado_alumno(self, obj):
        return obj.deuda.alumno.get_estado_display() if hasattr(obj.deuda.alumno, 'get_estado_display') else obj.deuda.alumno.estado
    get_estado_alumno.short_description = 'Estado del Alumno'
    get_estado_alumno.admin_order_field = 'deuda__alumno__estado'

    class Meta:
        permissions = (
            ('view_grafica', 'Puede ver la gráfica de ingresos y egresos'),
            ('view_abonos_hechos', 'Puede ver los abonos hechos'),
        )

# Registrar otros modelos si es necesario
@admin.register(Deuda)
class DeudaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'valor_total', 'saldo_pendiente', 'estado', 'fecha_creacion', 'get_estado_alumno')
    list_filter = ('estado', 'fecha_creacion', 'alumno__estado')
    readonly_fields = ('estado', 'saldo_pendiente')
    search_fields = ('alumno__nombres', 'alumno__primer_apellido')
    date_hierarchy = 'fecha_creacion'
    
    def has_change_permission(self, request, obj=None):
        # Si el objeto existe y es una deuda pagada, no permitir su edición
        if obj is not None and obj.estado == 'pagada':
            return False
        return super().has_change_permission(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        # Campos de solo lectura base
        readonly_fields = list(self.readonly_fields)
        
        # Si la deuda ya existe, ciertos campos no deberían ser editables
        if obj is not None:
            readonly_fields.extend(['alumno', 'valor_total'])
            
        return readonly_fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('alumno', 'alumno__grupo_actual__salon__sede__municipio')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(alumno__grupo_actual__salon__sede__municipio=request.user.municipio)
        return queryset
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtrar los alumnos disponibles en el formulario según el municipio del usuario
        if db_field.name == 'alumno' and not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            from academico.models import Alumno
            kwargs["queryset"] = Alumno.objects.filter(grupo_actual__salon__sede__municipio=request.user.municipio)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
    def get_estado_alumno(self, obj):
        return obj.alumno.get_estado_display() if hasattr(obj.alumno, 'get_estado_display') else obj.alumno.estado
    get_estado_alumno.short_description = 'Estado del Alumno'
    get_estado_alumno.admin_order_field = 'alumno__estado'


# @admin.register(Recibo)
# class ReciboAdmin(admin.ModelAdmin):
#     list_display = ('cuota', 'numero_recibo', 'fecha_emision', 'monto_abonado', 'metodo_pago')
#     list_filter = ('metodo_pago', 'fecha_emision')
#     search_fields = ('cuota__deuda__alumno__nombres', 'cuota__deuda__alumno__primer_apellido')
#     date_hierarchy = 'fecha_emision'

# @admin.register(HistorialModificacion)
# class HistorialModificacionAdmin(admin.ModelAdmin):
#     list_display = ('deuda', 'usuario', 'fecha_modificacion')
#     list_filter = ('fecha_modificacion', 'usuario')
#     search_fields = ('deuda__alumno__nombres', 'deuda__alumno__primer_apellido')
#     date_hierarchy = 'fecha_modificacion'

@admin.register(Egreso)
class EgresosAdmin(admin.ModelAdmin):
    list_display = ('sede', 'municipio', 'get_concepto_display', 'valor', 'estado', 'fecha')
    list_filter = ('estado', 'fecha', 'municipio', 'sede', 'concepto')
    search_fields = ('concepto', 'contratista')
    date_hierarchy = 'fecha'  # Navegación por fechas

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('sede', 'municipio')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(municipio=request.user.municipio)
        return queryset

    def get_concepto_display(self, obj):
        """Mostrar el nombre legible del concepto"""
        return dict(obj.CONCEPTO_CHOICES).get(obj.concepto, obj.concepto)
    get_concepto_display.short_description = 'Concepto'
    
    # Personalizar el formulario de edición
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            if db_field.name == "sede":
                # Filtrar sedes por municipio del usuario
                kwargs["queryset"] = Sede.objects.filter(municipio=request.user.municipio)
            elif db_field.name == "municipio":
                # Restringir la selección de municipio al del usuario
                from ubicaciones.models import Municipio
                kwargs["queryset"] = Municipio.objects.filter(id=request.user.municipio.id)
                kwargs["initial"] = request.user.municipio
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MetaRecaudo)
class MetaRecaudoAdmin(admin.ModelAdmin):
    list_display = ('mes', 'anio', 'valor_meta')
    list_filter = ('anio', 'mes')
    ordering = ('-anio', 'mes')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:  # Al crear una nueva meta
            # Establecer el año actual por defecto
            form.base_fields['anio'].initial = timezone.now().year
            # Establecer el mes actual por defecto
            form.base_fields['mes'].initial = timezone.now().month
        return form


@admin.register(TarifaClase)
class TarifaClaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'get_tipo_dia_display', 'get_horario_display', 'valor', 'activa', 'fecha_actualizacion')
    list_filter = ('tipo_dia', 'activa')
    search_fields = ('nombre',)
    list_editable = ('valor', 'activa')
    
    def get_tipo_dia_display(self, obj):
        return dict(obj.DIAS_SEMANA)[obj.tipo_dia]
    get_tipo_dia_display.short_description = 'Día'
    
    def get_horario_display(self, obj):
        if obj.horario:
            return dict(obj.HORARIOS)[obj.horario]
        return 'Cualquier horario'
    get_horario_display.short_description = 'Horario'
