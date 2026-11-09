from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from academico.models import Clase

class ClaseDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Clase
    template_name = 'academico/clase_detail.html'
    context_object_name = 'clase'

    def test_func(self):
        clase = self.get_object()
        return self.request.user.is_staff or self.request.user == clase.profesor

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clase = self.get_object()
        user = self.request.user

        puede_registrar = (
            user.is_superuser or 
            user.groups.filter(name='SecretariaAcademica').exists() or 
            (clase.estado != 'vista' and user == clase.profesor)
        )

        context.update({
            'titulo': f'Detalles de la Clase - {clase}',
            'puede_registrar': puede_registrar,
        })
        return context