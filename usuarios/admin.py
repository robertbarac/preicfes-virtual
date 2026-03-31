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
        if self.value() == 'si':
            return queryset.filter(subscriptions__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(subscriptions__isnull=True).distinct()

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
        if self.value() == 'si':
            return queryset.filter(subscriptions__active=True, subscriptions__end_date__gte=hoy).distinct()
        if self.value() == 'no':
            return queryset.exclude(subscriptions__active=True, subscriptions__end_date__gte=hoy).distinct()
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'get_full_name', 'numero_documento', 'telefono', 'role', 'tiene_suscripcion', 'suscripcion_activa', 'fin_suscripcion', 'is_active']
    list_filter = ['role', TieneSuscripcionFilter, SuscripcionActivaFilter, 'is_staff', 'is_active']
    search_fields = ('username', 'first_name', 'last_name', 'numero_documento', 'telefono', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Información de PreVirtual', {'fields': ('role', 'tipo_documento', 'numero_documento', 'telefono', 'creador')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de PreVirtual', {'fields': ('role', 'tipo_documento', 'numero_documento', 'telefono')}),
    )

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
