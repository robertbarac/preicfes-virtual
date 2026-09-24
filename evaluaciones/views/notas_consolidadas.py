from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from academico.models import Nota, Asistencia, Alumno
from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
from cartera.models import Deuda, Cuota
from ..models.talleres import IntentoTaller
from ..models.simulacros import IntentoSimulacro

class MisNotasView(LoginRequiredMixin, TemplateView):
    template_name = 'evaluaciones/mis_notas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Obtener alumno asociado si existe
        alumno = getattr(user, 'perfil_alumno', None)
        if not alumno:
            alumno = Alumno.objects.filter(usuario=user).first()
        
        # 1. Notas de Clases Presenciales (con materia, fecha y calificación)
        notas_presenciales = Nota.objects.none()
        asistencias = Asistencia.objects.none()
        simulacros_fisicos = ResultadoSimulacro.objects.none()
        simulacros_diagnosticos = ResultadoSimulacroDiagnostico.objects.none()
        cuotas = Cuota.objects.none()
        deuda = None

        if alumno:
            notas_presenciales = Nota.objects.filter(
                alumno=alumno, clase__estado='vista'
            ).select_related('clase', 'clase__materia', 'clase__grupo').order_by('-clase__fecha')
            
            # Asistencia a clases
            asistencias = Asistencia.objects.filter(
                alumno=alumno
            ).select_related('clase', 'clase__materia').order_by('-clase__fecha')

            # Simulacros Presenciales Normales y Diagnósticos
            simulacros_fisicos = ResultadoSimulacro.objects.filter(
                alumno=alumno
            ).select_related('simulacro').order_by('-fecha_realizacion')

            simulacros_diagnosticos = ResultadoSimulacroDiagnostico.objects.filter(
                alumno=alumno
            ).select_related('simulacro').order_by('-fecha_realizacion')

            # Cuotas y cartera
            try:
                deuda = alumno.deuda
                cuotas = deuda.cuotas.all().order_by('fecha_vencimiento')
            except Exception:
                deuda = None
                cuotas = Cuota.objects.none()

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

        is_presencial = user.groups.filter(name='Student').exists() or (alumno is not None)
        is_virtual = user.groups.filter(name='VirtualStudent').exists()

        context.update({
            'alumno': alumno,
            'notas_presenciales': notas_presenciales,
            'asistencias': asistencias,
            'total_asistencias': asistencias.count(),
            'asistencias_presente': asistencias.filter(asistio=True).count(),
            'asistencias_faltas': asistencias.filter(asistio=False).count(),
            'simulacros_fisicos': simulacros_fisicos,
            'simulacros_diagnosticos': simulacros_diagnosticos,
            'deuda': deuda,
            'cuotas': cuotas,
            'intentos_talleres': intentos_talleres,
            'intentos_simulacros_virtuales': intentos_simulacros_virtuales,
            'is_presencial': is_presencial,
            'is_virtual': is_virtual,
        })
        
        return context
