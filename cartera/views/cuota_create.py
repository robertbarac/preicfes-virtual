from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from cartera.models import Cuota, Deuda
from cartera.forms import CuotaForm

class CuotaCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Cuota
    form_class = CuotaForm
    template_name = 'cartera/cuota_form.html'
    
    def test_func(self):
        user = self.request.user
        if not user.is_staff:
            return False

        if user.is_superuser:
            return True

        grupos_autorizados = [
            'Cartera',
            'SecretariaCartera',
            'Auxiliar',
            'CoordinadorDepartamental',
        ]

        return user.groups.filter(name__in=grupos_autorizados).exists()


    def handle_no_permission(self):
        return redirect('login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deuda_id = self.kwargs.get('deuda_id')  # Obtener el ID de la deuda de la URL
        context['deuda'] = get_object_or_404(Deuda, id=deuda_id)  # Obtener la deuda
        return context

    def form_valid(self, form):
        cuota = form.save(commit=False)
        cuota.deuda = self.get_context_data()['deuda']  # Asociar la cuota con la deuda
        cuota.save()
        from cartera.utils_audit import registrar_log_audit, ADDITION
        registrar_log_audit(self.request.user, cuota, ADDITION, f"Cuota individual de ${cuota.monto} creada desde el sitio web.")
        return super().form_valid(form)

    def get_success_url(self):
        deuda_id = self.get_context_data()['deuda'].id  # Obtener el ID de la deuda
        alumno_id = self.get_context_data()['deuda'].alumno.id  # Obtener el ID del alumno asociado a la deuda
        return reverse('alumno_detail', kwargs={'pk': alumno_id})  # Redirigir a la vista de detalles del alumno
