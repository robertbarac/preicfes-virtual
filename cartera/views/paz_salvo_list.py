from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q

from academico.models import Alumno
from ubicaciones.models import Departamento, Municipio

class PazSalvoListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('cartera.view_cuota')
    model = Alumno
    template_name = 'cartera/paz_salvo_list.html'
    context_object_name = 'alumnos'
    paginate_by = 20

    def get_queryset(self):
        # Filtrar alumnos que:
        # 1. No sean becados
        # 2. Tengan deuda pagada
        # 3. Tengan saldo pendiente = 0
        # 4. Tengan al menos una cuota asociada
        # 5. El total de montos abonados sea igual al valor total de la deuda
        queryset = Alumno.objects.filter(
            es_becado=False,
            deuda__estado='pagada',
            deuda__saldo_pendiente=0,
            deuda__cuotas__isnull=False
        ).distinct().select_related(
            'deuda',
            'grupo_actual__salon__sede__municipio__departamento'
        ).order_by('primer_apellido', 'nombres')

        user = self.request.user
        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        search_query = self.request.GET.get('q')

        # Lógica de filtros por rol
        if user.is_superuser:
            if departamento_id:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento_id=departamento_id)
            if municipio_id:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
        elif user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            if hasattr(user, 'departamento') and user.departamento:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento=user.departamento)
                if municipio_id: # Permite al coordinador filtrar por municipio dentro de su depto
                    queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
            else:
                queryset = queryset.none() # No mostrar nada si no tiene depto asignado
        else: # Otros roles de staff
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio=user.municipio)
            else:
                queryset = queryset.none() # No mostrar nada si no tiene municipio asignado

        if search_query:
            queryset = queryset.filter(
                Q(nombres__icontains=search_query) |
                Q(primer_apellido__icontains=search_query) |
                Q(segundo_apellido__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        search_query = self.request.GET.get('q', '')

        context['search_query'] = search_query
        context['is_coordinador_or_auxiliar'] = user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()

        # Lógica de filtros para el contexto
        if user.is_superuser:
            context['departamentos'] = Departamento.objects.all()
            municipios_qs = Municipio.objects.all()
            if departamento_id:
                municipios_qs = municipios_qs.filter(departamento_id=departamento_id)
            context['municipios'] = municipios_qs
        elif context['is_coordinador_or_auxiliar']:
            if hasattr(user, 'departamento') and user.departamento:
                context['municipios'] = Municipio.objects.filter(departamento=user.departamento)
        
        context['departamento_seleccionado'] = departamento_id
        context['municipio_seleccionado'] = municipio_id
        
        # Contar el total de alumnos paz y salvo
        context['total_alumnos'] = self.get_queryset().count()
        
        return context
