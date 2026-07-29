from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from academico.models import Alumno
from ubicaciones.models import Departamento, Municipio, Sede
from academico.models import Grupo

class SaldosListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Alumno
    template_name = 'cartera/saldos_list.html'
    context_object_name = 'alumnos'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        # Base queryset with necessary relationships to optimize queries
        queryset = Alumno.objects.select_related(
            'deuda', 
            'grupo_actual', 
            'grupo_actual__salon__sede', 
            'municipio', 
            'municipio__departamento'
        ).filter(
            # Optional: only show active students if required, or everyone who has debts.
            # Assuming we want all students that have a Deuda
            deuda__isnull=False
        )

        # Apply filters from request.GET
        grupo_id = self.request.GET.get('grupo')
        sede_id = self.request.GET.get('sede')
        municipio_id = self.request.GET.get('municipio')
        departamento_id = self.request.GET.get('departamento')

        if grupo_id:
            queryset = queryset.filter(grupo_actual_id=grupo_id)
        if sede_id:
            queryset = queryset.filter(grupo_actual__salon__sede_id=sede_id)
        if municipio_id:
            queryset = queryset.filter(municipio_id=municipio_id)
        if departamento_id:
            queryset = queryset.filter(municipio__departamento_id=departamento_id)

        # Ordem by nombres and primer_apellido
        return queryset.order_by('nombres', 'primer_apellido')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass filter options
        context['grupos'] = Grupo.objects.all().order_by('codigo')
        context['sedes'] = Sede.objects.all().order_by('nombre')
        context['municipios'] = Municipio.objects.all().order_by('nombre')
        context['departamentos'] = Departamento.objects.all().order_by('nombre')

        # Current filter values for preserving state in the template
        context['current_grupo'] = self.request.GET.get('grupo', '')
        context['current_sede'] = self.request.GET.get('sede', '')
        context['current_municipio'] = self.request.GET.get('municipio', '')
        context['current_departamento'] = self.request.GET.get('departamento', '')

        return context
