from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone

from cartera.models import Cuota

class MantenimientoCarteraView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'cartera/mantenimiento_cartera.html'
    
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener cuotas que necesitan actualización
        queryset = Cuota.objects.filter(
            estado='emitida',
            fecha_vencimiento__lt=timezone.localtime(timezone.now()).date()
        )
        
        user = self.request.user
        # Filtrar por rol
        if not user.is_superuser:
            if user.groups.filter(name='CoordinadorDepartamental').exists():
                if user.departamento:
                    queryset = queryset.filter(
                        deuda__alumno__municipio__departamento=user.departamento
                    )
            else:
                queryset = queryset.filter(
                    deuda__alumno__grupo_actual__salon__sede__municipio=self.request.user.municipio
                )
        
        context['cuotas_por_actualizar'] = queryset.count()
        return context
    
    def post(self, request, *args, **kwargs):
        # Obtener cuotas que necesitan actualización
        queryset = Cuota.objects.filter(
            estado='emitida',
            fecha_vencimiento__lt=timezone.localtime(timezone.now()).date()
        )
        
        user = self.request.user
        # Filtrar por rol
        if not user.is_superuser:
            if user.groups.filter(name='CoordinadorDepartamental').exists():
                if user.departamento:
                    queryset = queryset.filter(
                        deuda__alumno__municipio__departamento=user.departamento
                    )
            else:
                queryset = queryset.filter(
                    deuda__alumno__grupo_actual__salon__sede__municipio=self.request.user.municipio
                )
        
        # Actualizar estados
        cuotas_actualizadas = queryset.count()
        queryset.update(estado='vencida')
        
        # Agregar mensaje y contexto
        context = self.get_context_data(**kwargs)
        context['cuotas_actualizadas'] = cuotas_actualizadas
        return self.render_to_response(context)