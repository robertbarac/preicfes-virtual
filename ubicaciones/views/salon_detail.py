from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count

from ubicaciones.models import Salon
from academico.models import Grupo

class SalonDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Salon
    template_name = 'ubicaciones/salon_detail.html'
    context_object_name = 'salon'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salon = self.get_object()
        
        # Obtener los grupos que usan este salón
        grupos = Grupo.objects.filter(salon=salon).select_related(
            'salon', 'salon__sede', 'salon__sede__municipio'
        ).annotate(
            sillas_ocupadas=Count('alumnos_actuales')
        )
        
        context.update({
            'grupos': grupos,
            'titulo': f'Detalles del Salón {salon}'
        })
        return context