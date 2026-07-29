from django.contrib import admin
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Alumno, Clase, Grupo, Materia, Nota, Asistencia
from ubicaciones.models import Municipio, Salon

class AlumnoAdminForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        
        # Validación de la identificación: solo números y no duplicado
        identificacion = cleaned_data.get('identificacion')
        if identificacion:
            ident_clean = str(identificacion).strip()
            # Quitamos espacios y validamos que sean solo dígitos
            if not ident_clean.isdigit():
                raise ValidationError({
                    'identificacion': 'La identificación no debe tener puntos, espacios ni letras. Solo números (0-9).'
                })
            
            qs = Alumno.objects.filter(identificacion=ident_clean)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError({
                    'identificacion': f'Ya existe un alumno registrado con la identificación {ident_clean}.'
                })
        
        # Validación: al menos un celular de los padres no debe ser nulo, vacío ni 'SIN DATOS'
        celular_padre = cleaned_data.get('celular_padre')
        celular_madre = cleaned_data.get('celular_madre')
        
        # Un celular es válido si NO es None, NO está vacío al quitar espacios ('') y NO es igual a 'SIN DATOS'
        padre_valido = False
        if celular_padre is not None and str(celular_padre).strip() and str(celular_padre).strip().upper() != 'SIN DATOS':
            padre_valido = True
            
        madre_valida = False
        if celular_madre is not None and str(celular_madre).strip() and str(celular_madre).strip().upper() != 'SIN DATOS':
            madre_valida = True
        
        if not padre_valido and not madre_valida:
            raise ValidationError(
                'Debe ingresar el celular del padre o el celular de la madre. Al menos uno es obligatorio y no puede quedar vacío.'
            )
            
        return cleaned_data


class EstadoDeudaFilter(admin.SimpleListFilter):
    title = 'Estado de Deuda'
    parameter_name = 'estado_deuda'

    def lookups(self, request, model_admin):
        return (
            ('emitida', 'Emitida (Pendiente)'),
            ('pagada', 'Pagada'),
            ('sin_deuda', 'Sin Deuda'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'emitida':
            return queryset.filter(deuda__estado='emitida')
        elif self.value() == 'pagada':
            return queryset.filter(deuda__estado='pagada')
        elif self.value() == 'sin_deuda':
            return queryset.filter(deuda__isnull=True)
        return queryset


from datetime import datetime


class FechaCulminacionAlumnoRangeFilter(admin.SimpleListFilter):
    title = 'Fecha Culminación (Rango)'
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
                queryset = queryset.filter(fecha_culminacion__gte=fecha_desde)
            except ValueError:
                pass

        if hasta:
            try:
                fecha_hasta = datetime.strptime(hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_culminacion__lte=fecha_hasta)
            except ValueError:
                pass

        return queryset

    def choices(self, changelist):
        return [{
            'query_dict': self.request_get,
            'value_desde': self.value_desde or '',
            'value_hasta': self.value_hasta or '',
            'parameter_name_desde': self.parameter_name_desde,
            'parameter_name_hasta': self.parameter_name_hasta,
        }]


def procesar_transicion_limbo(alumno):
    if alumno.estado != 'limbo':
        return
    if alumno.grupo_actual and alumno.grupo_actual.codigo.startswith('LIMBO'):
        return

    sede = None
    if alumno.grupo_actual and alumno.grupo_actual.salon:
        sede = alumno.grupo_actual.salon.sede
    elif alumno.municipio:
        sede = Sede.objects.filter(municipio=alumno.municipio).first()

    if not sede:
        sede = Sede.objects.first()

    if sede:
        grupo_limbo = Grupo.objects.filter(
            codigo__istartswith='LIMBO',
            salon__sede=sede
        ).first()

        if not grupo_limbo:
            salon_limbo, _ = Salon.objects.get_or_create(
                sede=sede,
                numero=999,
                defaults={'capacidad_sillas': 999}
            )
            grupo_limbo = Grupo.objects.create(
                salon=salon_limbo,
                codigo=f'LIMBO-{sede.nombre[:10].upper().replace(" ", "")}'
            )

        alumno.grupo_actual = grupo_limbo


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    form = AlumnoAdminForm
    list_display = ('nombres', 'primer_apellido', 'estado', 'fecha_ingreso', 'fecha_culminacion', 'tipo_programa', 'municipio', 'get_departamento', 'grupo_actual', 'nombres_padre', 'celular_padre', 'nombres_madre', 'celular_madre')
    list_editable = ('estado',)
    list_filter = ('estado', EstadoDeudaFilter, FechaCulminacionAlumnoRangeFilter, 'tipo_programa', 'es_becado', 'municipio', 'municipio__departamento', 'fecha_ingreso', 'grupo_actual')
    search_fields = ('nombres', 'primer_apellido', 'segundo_apellido', 'identificacion', 'nombres_padre', 'celular_padre', 'nombres_madre', 'celular_madre')
    actions = ['enviar_a_limbo']

    @admin.action(description='🔒 Enviar alumnos seleccionados al Limbo')
    def enviar_a_limbo(self, request, queryset):
        count = 0
        for alumno in queryset:
            alumno.estado = 'limbo'
            procesar_transicion_limbo(alumno)
            alumno.save(update_fields=['estado', 'grupo_actual'])
            count += 1
        self.message_user(request, f'{count} alumnos fueron enviados al Limbo exitosamente.')

    def save_model(self, request, obj, form, change):
        if obj.estado == 'limbo':
            procesar_transicion_limbo(obj)
        super().save_model(request, obj, form, change)
    
    def get_departamento(self, obj):
        return obj.municipio.departamento if obj.municipio and obj.municipio.departamento else None
    get_departamento.short_description = 'Departamento'
    get_departamento.admin_order_field = 'municipio__departamento'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('municipio', 'grupo_actual')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(municipio=request.user.municipio)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtrar municipios según el usuario logeado
        if db_field.name == "municipio":
            usuario = request.user
            if not usuario.is_superuser and usuario.municipio:
                # Mostrar solo el municipio del usuario
                kwargs["queryset"] = Municipio.objects.filter(id=usuario.municipio.id)
            else:
                # Mostrar todos los municipios si es superusuario
                kwargs["queryset"] = Municipio.objects.all()

        # Filtrar grupos según el municipio del alumno
        if db_field.name == "grupo_actual":
            alumno_id = request.resolver_match.kwargs.get('object_id')
            if alumno_id:
                alumno = Alumno.objects.get(id=alumno_id)
                if alumno.municipio:
                    # Filtrar grupos por el municipio del alumno
                    kwargs["queryset"] = Grupo.objects.filter(salon__sede__municipio=alumno.municipio)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# admin.site.register(Alumno, AlumnoAdmin)

@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'salon')
    list_filter = ('salon', 'salon__sede__municipio')
    search_fields = ('codigo', 'salon__numero')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('salon', 'salon__sede', 'salon__sede__municipio')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(salon__sede__municipio=request.user.municipio)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "salon":
            # Obtener el usuario logeado
            usuario = request.user

            # Filtrar salones por ciudad si el usuario no es superusuario
            if not usuario.is_superuser and usuario.municipio:
                kwargs["queryset"] = Salon.objects.filter(
                    sede__municipio=usuario.municipio
                ).order_by('numero')  # Ordenar por nombre del salón
            else:
                # Mostrar todos los salones si el usuario es superusuario
                kwargs["queryset"] = Salon.objects.order_by('numero')  # Ordenar por nombre del salón

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Clase)
class ClaseAdmin(admin.ModelAdmin):
    list_display = ('materia', 'fecha', 'horario', 'salon', 'profesor', 'grupo', 'estado')
    list_filter = ('estado', 'fecha', 'horario', 'salon', 'materia', 'grupo__salon__sede', 'profesor', 'grupo__salon__sede__municipio', 'grupo__codigo')
    search_fields = ('materia__nombre', 'profesor__username', 'grupo__codigo', 'estado')

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'grupo__salon__sede__municipio__departamento', 'profesor', 'materia'
        )
        user = request.user

        if user.is_superuser:
            return queryset

        if user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            if hasattr(user, 'departamento') and user.departamento:
                return queryset.filter(grupo__salon__sede__municipio__departamento=user.departamento)
            else:
                return queryset.none() # No mostrar nada si no tiene departamento asignado

        if hasattr(user, 'municipio') and user.municipio:
            return queryset.filter(grupo__salon__sede__municipio=user.municipio)
        
        return queryset.none() # Por defecto, no mostrar nada si no cumple ninguna condición

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser:
            departamento = getattr(user, 'departamento', None)
            municipio = getattr(user, 'municipio', None)

            if departamento:
                if db_field.name == "grupo":
                    kwargs["queryset"] = Grupo.objects.filter(salon__sede__municipio__departamento=departamento)
                elif db_field.name == "salon":
                    kwargs["queryset"] = Salon.objects.filter(sede__municipio__departamento=departamento)
            elif municipio:
                if db_field.name == "grupo":
                    kwargs["queryset"] = Grupo.objects.filter(salon__sede__municipio=municipio)
                elif db_field.name == "salon":
                    kwargs["queryset"] = Salon.objects.filter(sede__municipio=municipio)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)



@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    # Campos que se mostrarán en la lista de registros
    list_display = ('alumno', 'clase', 'nota')
    
    # Filtros laterales
    list_filter = ('clase', 'alumno')
    
    list_editable = ('nota',)
    
    # Campos de búsqueda
    search_fields = ('alumno__nombres', 'alumno__primer_apellido', 'clase__materia__nombre')
    
    # Orden por defecto
    ordering = ('clase', 'alumno')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('alumno', 'clase', 'alumno__municipio')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(alumno__municipio=request.user.municipio)
        return queryset
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            if db_field.name == "alumno":
                kwargs["queryset"] = Alumno.objects.filter(municipio=request.user.municipio)
            elif db_field.name == "clase":
                kwargs["queryset"] = Clase.objects.filter(grupo__salon__sede__municipio=request.user.municipio)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('clase', 'alumno', 'asistio')
    list_editable = ('asistio',)
    list_filter = ('asistio', 'clase__fecha')
    search_fields = ('alumno__nombres', 'alumno__primer_apellido', 'clase__materia__nombre')
    # Acciones personalizadas
    actions = ['marcar_asistio', 'marcar_no_asistio']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('alumno', 'clase', 'alumno__municipio')
        # Si no es superuser, filtrar por municipio del usuario
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            queryset = queryset.filter(alumno__municipio=request.user.municipio)
        return queryset
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'municipio') and request.user.municipio:
            if db_field.name == "alumno":
                kwargs["queryset"] = Alumno.objects.filter(municipio=request.user.municipio)
            elif db_field.name == "clase":
                kwargs["queryset"] = Clase.objects.filter(grupo__salon__sede__municipio=request.user.municipio)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
    def marcar_asistio(self, request, queryset):
        queryset.update(asistio=True)
    marcar_asistio.short_description = "Marcar como asistió"
    
    def marcar_no_asistio(self, request, queryset):
        queryset.update(asistio=False)
    marcar_no_asistio.short_description = "Marcar como no asistió"