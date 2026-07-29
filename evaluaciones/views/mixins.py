from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect

def es_personal_docente_o_staff(user):
    if not user.is_authenticated:
        return False
    group_names = set(user.groups.values_list('name', flat=True))
    return (
        user.is_superuser or 
        user.is_staff or 
        getattr(user, 'role', '') in ['admin', 'teacher'] or 
        'Profesor' in group_names or 
        'Teacher' in group_names or 
        'CoordinadorDepartamental' in group_names or 
        'SecretariaAcademica' in group_names
    )

class DocenteOStaffPermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return es_personal_docente_o_staff(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "No tienes permisos suficientes para realizar esta acción de gestión (Crear/Editar/Eliminar).")
            return redirect('evaluaciones:taller_list')
        return super().handle_no_permission()
