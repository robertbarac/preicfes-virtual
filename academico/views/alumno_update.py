from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy

from academico.models import Alumno
from academico.forms import AlumnoForm

class AlumnoUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Alumno
    form_class = AlumnoForm
    template_name = 'academico/alumno_form.html'
    success_url = reverse_lazy('alumnos_list')

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        return redirect('login')