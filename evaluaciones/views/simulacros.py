from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from ..models.simulacros import Simulacro
from ..forms import SimulacroForm
from curriculo.views.mixins import HistorialMixin

class SimulacroCreateView(HistorialMixin, CreateView):
    model = Simulacro
    form_class = SimulacroForm
    template_name = 'evaluaciones/simulacro_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        modulo_id = self.request.GET.get('modulo')
        if modulo_id:
            initial['modulo'] = modulo_id
        return initial

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

class SimulacroUpdateView(HistorialMixin, UpdateView):
    model = Simulacro
    form_class = SimulacroForm
    template_name = 'evaluaciones/simulacro_form.html'
    
    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

from django.views.generic import DetailView

class SimulacroDetailView(DetailView):
    model = Simulacro
    template_name = 'evaluaciones/simulacro_detail.html'
    context_object_name = 'simulacro'
