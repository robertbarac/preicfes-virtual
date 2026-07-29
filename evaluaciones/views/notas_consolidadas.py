from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from academico.models import Nota
from simulacros.models import ResultadoSimulacro
from ..models.talleres import IntentoTaller
from ..models.simulacros import IntentoSimulacro

class MisNotasView(LoginRequiredMixin, TemplateView):
    template_name = 'evaluaciones/mis_notas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 1. Notas de Clases Presenciales
        notas_presenciales = Nota.objects.filter(
            alumno__usuario=user
        ).select_related('clase', 'clase__materia', 'clase__grupo').order_by('-clase__fecha')
        
        # 2. Resultados de Simulacros Físicos / Ópticos (OMR)
        simulacros_fisicos = ResultadoSimulacro.objects.filter(
            alumno__usuario=user
        ).select_related('simulacro').order_by('-fecha_realizacion')

        # 3. Intentos de Talleres Virtuales
        intentos_talleres = IntentoTaller.objects.filter(
            usuario=user,
            fecha_fin__isnull=False
        ).select_related('taller', 'taller__modulo').order_by('-fecha_fin')

        # 4. Intentos de Simulacros Virtuales
        intentos_simulacros_virtuales = IntentoSimulacro.objects.filter(
            usuario=user,
            fecha_fin__isnull=False
        ).select_related('simulacro').order_by('-fecha_fin')

        context.update({
            'notas_presenciales': notas_presenciales,
            'simulacros_fisicos': simulacros_fisicos,
            'intentos_talleres': intentos_talleres,
            'intentos_simulacros_virtuales': intentos_simulacros_virtuales,
            'is_presencial': user.role == 'student',
            'is_virtual': user.role == 'virtual_student',
        })
        
        return context
