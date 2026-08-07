from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect

def tiene_permiso_evaluaciones(user, codename=None):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if codename:
        return user.has_perm(f'evaluaciones.{codename}')
    return (
        user.has_perm('evaluaciones.add_taller') or 
        user.has_perm('evaluaciones.change_taller') or 
        user.has_perm('evaluaciones.add_bloquecontexto') or 
        user.has_perm('evaluaciones.change_bloquecontexto')
    )

def es_personal_docente_o_staff(user):
    return tiene_permiso_evaluaciones(user)

class DocenteOStaffPermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return tiene_permiso_evaluaciones(self.request.user, self.permission_required)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "No tienes permisos suficientes para realizar esta acción de gestión.")
            return redirect('evaluaciones:taller_list')
        return super().handle_no_permission()
