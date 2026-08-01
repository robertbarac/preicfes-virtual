from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from usuarios.models import User
from ubicaciones.models import Municipio

class ProfesorListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'usuarios/profesor_list.html'
    context_object_name = 'profesores'
    login_url = 'login'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_queryset(self):
        queryset = User.objects.filter(groups__name__in=['Profesor', 'Teacher']).distinct()
        
        user = self.request.user
        if user.is_superuser:
            pass
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if hasattr(user, 'departamento') and user.departamento:
                queryset = queryset.filter(municipio__departamento=user.departamento)
        else:
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(municipio=user.municipio)

        municipio_id = self.request.GET.get('municipio')
        if municipio_id:
            queryset = queryset.filter(municipio_id=municipio_id)
            
        q = self.request.GET.get('q', '').strip()
        if q:
            words = q.split()
            search_query = Q()
            for word in words:
                search_query &= (
                    Q(first_name__icontains=word) |
                    Q(last_name__icontains=word) |
                    Q(username__icontains=word) |
                    Q(numero_documento__icontains=word) |
                    Q(telefono__icontains=word) |
                    Q(email__icontains=word)
                )
            queryset = queryset.filter(search_query)
            
        return queryset.order_by('first_name', 'last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Listado de Profesores'
        user = self.request.user
        if user.is_superuser:
            context['municipios'] = Municipio.objects.all()
        elif user.groups.filter(name='CoordinadorDepartamental').exists() and hasattr(user, 'departamento') and user.departamento:
            context['municipios'] = Municipio.objects.filter(departamento=user.departamento)
        else:
            context['municipios'] = Municipio.objects.filter(id=user.municipio.id) if hasattr(user, 'municipio') and user.municipio else Municipio.objects.none()
        return context
