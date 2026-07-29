from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages

from ..models import Alumno
from ..forms import AlumnoForm

class AlumnoCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Alumno
    form_class = AlumnoForm
    template_name = 'academico/alumno_form.html'
    success_url = reverse_lazy('alumnos_list')

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        return redirect('login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Agregar Alumno'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Alumno agregado exitosamente.')
        return super().form_valid(form)