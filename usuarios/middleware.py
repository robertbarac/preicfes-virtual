from django.shortcuts import redirect
from django.contrib import messages

class RestringirAccesoAulaVirtualMiddleware:
    """
    Middleware que restringe el acceso al Portal 1 (Aula Virtual: /programa/, /evaluaciones/, /contenidos/)
    a roles que no sean Superuser o Teachers.
    Usuarios de los grupos Auxiliar, SecretariaAcademica, SecretariaCartera, CoordinadorDepartamental, ObservadorColegio
    son redirigidos al Portal 2 (Cartera & Gestión Académica) si intentan acceder al Aula Virtual.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        user = request.user
        path = request.path_info

        # Solo aplicamos la restricción si intentan ingresar a rutas del Aula Virtual
        if path.startswith('/programa/') or path.startswith('/evaluaciones/') or path.startswith('/contenidos/'):
            # Superusuarios y Docentes (grupos Profesor/Teacher) SI tienen acceso a ambos portales
            if user.is_superuser or user.es_docente:
                return self.get_response(request)

            group_names = set(user.groups.values_list('name', flat=True))
            if 'Profesor' in group_names or 'Teacher' in group_names:
                return self.get_response(request)

            # Si el usuario pertenece a grupos de gestión (Auxiliar, Secretarías, Coordinador, Observador), redirigir
            if group_names.intersection({'Auxiliar', 'SecretariaAcademica', 'SecretariaCartera', 'CoordinadorDepartamental', 'ObservadorColegio'}):
                messages.warning(request, "Tu perfil únicamente tiene acceso al Portal de Cartera & Gestión Académica.")
                return redirect('alumnos_list')

        return self.get_response(request)
