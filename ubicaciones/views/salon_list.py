from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, F

from ubicaciones.models import Salon, Sede
from academico.models import Grupo

class SalonListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Salon
    template_name = 'ubicaciones/salon_list.html'
    context_object_name = 'salones'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = Salon.objects.select_related('sede', 'sede__municipio')
        
        user = self.request.user
        # Filtrado por rol
        if user.is_superuser:
            pass  # Superuser ve todo
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                queryset = queryset.filter(sede__municipio__departamento=user.departamento)
        else:
            # Otro personal (staff) ve solo su municipio
            queryset = queryset.filter(sede__municipio=user.municipio)
        
        # Filtros
        sede = self.request.GET.get('sede')
        ciudad = self.request.GET.get('ciudad')
        capacidad_min = self.request.GET.get('capacidad_min')
        capacidad_max = self.request.GET.get('capacidad_max')
        
        if sede:
            queryset = queryset.filter(sede_id=sede)
        if ciudad:
            queryset = queryset.filter(sede__municipio__nombre=ciudad)
        if capacidad_min:
            queryset = queryset.filter(capacidad_sillas__gte=capacidad_min)
        if capacidad_max:
            queryset = queryset.filter(capacidad_sillas__lte=capacidad_max)

        return queryset.order_by('sede__municipio__nombre', 'sede__nombre', 'numero')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        # Lógica de contexto por rol
        if user.is_superuser:
            context['sedes'] = Sede.objects.all()
            context['ciudades'] = Sede.objects.values_list('municipio__nombre', flat=True).distinct()
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                context['sedes'] = Sede.objects.filter(municipio__departamento=user.departamento)
                context['ciudades'] = Sede.objects.filter(municipio__departamento=user.departamento).values_list('municipio__nombre', flat=True).distinct()
            else:
                context['sedes'] = Sede.objects.none()
                context['ciudades'] = []
        else:
            # Otro personal (staff) ve solo su municipio
            context['sedes'] = Sede.objects.filter(municipio=user.municipio)
            context['ciudades'] = [user.municipio.nombre]
        
        context['titulo'] = 'Lista de Salones'
        context['is_coordinador'] = user.groups.filter(name='CoordinadorDepartamental').exists()
        return context