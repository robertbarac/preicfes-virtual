from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from suscripciones.models import Subscription
from django.utils import timezone

class TieneSuscripcionFilter(admin.SimpleListFilter):
    title = '¿Tiene Suscripción?'
    parameter_name = 'tiene_suscripcion'

    def lookups(self, request, model_admin):
        return (
            ('si', 'Sí'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        user_ids = Subscription.objects.values_list('user_id', flat=True)
        if self.value() == 'si':
            return queryset.filter(id__in=user_ids)
        if self.value() == 'no':
            return queryset.exclude(id__in=user_ids)

class SuscripcionActivaFilter(admin.SimpleListFilter):
    title = 'Suscripción Activa'
    parameter_name = 'susc_activa'

    def lookups(self, request, model_admin):
        return (
            ('si', 'Sí (Vigente)'),
            ('no', 'No (Vencida/Inactiva)'),
        )

    def queryset(self, request, queryset):
        hoy = timezone.now().date()
        active_user_ids = Subscription.objects.filter(active=True, end_date__gte=hoy).values_list('user_id', flat=True)
        if self.value() == 'si':
            return queryset.filter(id__in=active_user_ids)
        if self.value() == 'no':
            return queryset.exclude(id__in=active_user_ids)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'get_full_name', 'numero_documento', 'telefono', 'role', 'get_grupo', 'departamento', 'municipio', 'sede', 'is_superuser', 'is_staff', 'is_active', 'tiene_suscripcion']
    list_filter = ['groups', 'role', 'departamento', 'municipio', 'sede', 'is_superuser', 'is_staff', 'is_active', TieneSuscripcionFilter, SuscripcionActivaFilter]
    search_fields = ('username', 'first_name', 'last_name', 'numero_documento', 'telefono', 'email')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email', 'tipo_documento', 'numero_documento', 'telefono')}),
        ('Ubicación y Sede', {'fields': ('departamento', 'municipio', 'sede')}),
        ('Configuración PreVirtual', {'fields': ('role', 'programa', 'programas_docente', 'creador')}),
        ('Permisos y Grupos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'tipo_documento', 'numero_documento', 'telefono', 'role', 'departamento', 'municipio', 'sede'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions', 'programas_docente')

    def get_grupo(self, obj):
        if obj.groups.exists():
            return ", ".join([g.name for g in obj.groups.all()])
        return 'Sin grupo'
    get_grupo.short_description = 'Grupo(s)'

    def delete_queryset(self, request, queryset):
        pks = list(queryset.values_list('pk', flat=True))
        User.objects.filter(pk__in=pks).delete()

    def tiene_suscripcion(self, obj):
        return obj.subscriptions.exists()
    tiene_suscripcion.boolean = True
    tiene_suscripcion.short_description = 'Tiene Suscripción'

    def suscripcion_activa(self, obj):
        hoy = timezone.now().date()
        return obj.subscriptions.filter(active=True, end_date__gte=hoy).exists()
    suscripcion_activa.boolean = True
    suscripcion_activa.short_description = 'Susc. Activa'

    def fin_suscripcion(self, obj):
        suscripcion = obj.subscriptions.order_by('-end_date').first()
        if suscripcion:
            return suscripcion.end_date
        return '-'
    fin_suscripcion.short_description = 'Fin Suscripción'

from .models import ConfiguracionPlataforma

@admin.register(ConfiguracionPlataforma)
class ConfiguracionPlataformaAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser and request.user.username == 'robertbarac'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and request.user.username == 'robertbarac'

    def has_add_permission(self, request):
        if not (request.user.is_superuser and request.user.username == 'robertbarac'):
            return False
        try:
            if ConfiguracionPlataforma.objects.exists():
                return False
        except Exception:
            pass
        return True

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.user.username == 'robertbarac'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and request.user.username == 'robertbarac'
