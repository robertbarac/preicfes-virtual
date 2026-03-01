from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'first_name', 'last_name', 'numero_documento', 'role', 'is_staff', 'is_active']
    list_filter = ['role', 'is_staff', 'is_superuser', 'is_active']
    search_fields = UserAdmin.search_fields + ('numero_documento',)
    fieldsets = UserAdmin.fieldsets + (
        ('Información de PreVirtual', {'fields': ('role', 'tipo_documento', 'numero_documento', 'creador')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de PreVirtual', {'fields': ('role', 'tipo_documento', 'numero_documento')}),
    )
