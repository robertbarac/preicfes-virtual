from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from academico.models import Clase

class ClaseDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Clase
    template_name = 'academico/clase_detail.html'
    context_object_name = 'clase'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clase = self.get_object()
        
        context.update({
            'titulo': f'Detalles de la Clase - {clase}'
        })
        return context