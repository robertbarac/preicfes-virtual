# Django imports
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic.edit import DeleteView

# Local imports
from cartera.models import Cuota

class CuotaDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Cuota
    template_name = 'cartera/cuota_confirm_delete.html'
    
    def test_func(self):
        # vvgomez tiene acceso total para eliminar cualquier cuota.
        if self.request.user.username == 'vvgomez':
            return True

        # Para otros usuarios, permitir solo si son staff/superuser Y la cuota no tiene abonos.
        cuota = self.get_object()
        user_is_authorized = self.request.user.is_staff or self.request.user.is_superuser
        cuota_is_deletable = cuota.monto_abonado == 0
        return user_is_authorized and cuota_is_deletable

    def handle_no_permission(self):
        return redirect('login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuota = self.get_object()
        context['alumno'] = cuota.deuda.alumno
        return context

    def form_valid(self, form):
        cuota = self.get_object()
        from cartera.utils_audit import registrar_log_audit, DELETION
        registrar_log_audit(self.request.user, cuota, DELETION, f"Cuota de ${cuota.monto} (vencimiento: {cuota.fecha_vencimiento}) eliminada desde el sitio web.")
        return super().form_valid(form)

    def get_success_url(self):
        cuota = self.get_object()
        return reverse('alumno_detail', kwargs={'pk': cuota.deuda.alumno.id})