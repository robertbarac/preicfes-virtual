from django.views.generic import View
from django.shortcuts import render
from django.db.models import Avg
from django.utils import timezone

from academico.models import Alumno, Asistencia, Nota, Inasistencia
from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
from cartera.models import Deuda, Cuota
from evaluaciones.models.simulacros import IntentoSimulacro
from evaluaciones.models.talleres import IntentoTaller


class ConsultaEstudianteView(View):
    template_name = 'academico/consulta_estudiante.html'

    def get(self, request, *args, **kwargs):
        identificacion = request.GET.get('identificacion', '').strip()
        context = {
            'identificacion': identificacion,
            'alumno': None,
            'busqueda_realizada': False,
            'error_mensaje': None,
        }

        if identificacion:
            context['busqueda_realizada'] = True
            
            # Buscar por identificación ignorando mayúsculas/minúsculas y espacios
            alumno = Alumno.objects.filter(
                identificacion__iexact=identificacion
            ).select_related(
                'municipio', 
                'municipio__departamento', 
                'grupo_actual', 
                'grupo_actual__salon', 
                'grupo_actual__salon__sede',
                'usuario'
            ).first()

            if not alumno:
                context['error_mensaje'] = f"No se encontró ningún estudiante con el número de documento '{identificacion}'."
                return render(request, self.template_name, context)

            context['alumno'] = alumno

            # 1. Asistencias a Clases
            asistencias_qs = Asistencia.objects.filter(
                alumno=alumno
            ).select_related('clase', 'clase__materia').order_by('-clase__fecha')
            
            inasistencias_justificadas = {
                inasistencia.clase_id: inasistencia
                for inasistencia in Inasistencia.objects.filter(alumno=alumno)
            }

            asistencias_lista = []
            for a in asistencias_qs:
                if not a.asistio:
                    inasistencia_obj = inasistencias_justificadas.get(a.clase_id)
                    a.tiene_justificacion = inasistencia_obj is not None and inasistencia_obj.justificada
                    a.motivo_justificacion = inasistencia_obj.motivo if inasistencia_obj else ""
                else:
                    a.tiene_justificacion = False
                    a.motivo_justificacion = ""
                asistencias_lista.append(a)

            total_asistencias = len(asistencias_lista)
            asistencias_presente = sum(1 for a in asistencias_lista if a.asistio)
            asistencias_faltas = sum(1 for a in asistencias_lista if not a.asistio)
            porcentaje_asistencia = round((asistencias_presente / total_asistencias * 100), 1) if total_asistencias > 0 else 0

            context.update({
                'asistencias': asistencias_lista,
                'total_asistencias': total_asistencias,
                'asistencias_presente': asistencias_presente,
                'asistencias_faltas': asistencias_faltas,
                'porcentaje_asistencia': porcentaje_asistencia,
            })

            # 2. Notas de clases presenciales
            notas = Nota.objects.filter(
                alumno=alumno, 
                clase__estado='vista'
            ).select_related('clase__materia').order_by('-clase__fecha')

            promedios_materias = Nota.objects.filter(
                alumno=alumno,
                clase__estado='vista'
            ).values('clase__materia__nombre').annotate(
                promedio=Avg('nota')
            ).order_by('clase__materia__nombre')

            context.update({
                'notas': notas,
                'promedios_materias': promedios_materias,
            })

            # 3. Simulacros Físicos / Presenciales Estándar
            simulacros_fisicos = alumno.resultados_simulacros.select_related(
                'simulacro'
            ).order_by('-fecha_realizacion')

            # 4. Simulacros Diagnósticos Presenciales
            simulacros_diagnosticos = alumno.resultados_simulacros_diagnosticos.select_related(
                'simulacro'
            ).order_by('-fecha_realizacion')

            # 5. Simulacros Virtuales y Talleres (si tiene usuario vinculado)
            simulacros_virtuales = []
            intentos_talleres = []
            if alumno.usuario:
                simulacros_virtuales = IntentoSimulacro.objects.filter(
                    usuario=alumno.usuario,
                    fecha_fin__isnull=False
                ).select_related('simulacro').order_by('-fecha_fin')

                intentos_talleres = IntentoTaller.objects.filter(
                    usuario=alumno.usuario,
                    fecha_fin__isnull=False
                ).select_related('taller', 'taller__modulo', 'clase', 'clase__materia').order_by('-fecha_fin')

            context.update({
                'simulacros_fisicos': simulacros_fisicos,
                'simulacros_diagnosticos': simulacros_diagnosticos,
                'simulacros_virtuales': simulacros_virtuales,
                'intentos_talleres': intentos_talleres,
            })

            # 6. Cartera y Cuotas (Solo visualización / Lectura)
            try:
                deuda = alumno.deuda
                cuotas = list(deuda.cuotas.all().order_by('fecha_vencimiento'))
                today = timezone.localtime(timezone.now()).date()

                for cuota in cuotas:
                    if cuota.monto_abonado >= cuota.monto:
                        cuota.estado_calculado = "Pagada"
                        cuota.badge_color = "bg-emerald-100 text-emerald-800 border-emerald-200"
                    elif cuota.monto_abonado > 0:
                        cuota.estado_calculado = "Abono Parcial"
                        cuota.badge_color = "bg-amber-100 text-amber-800 border-amber-200"
                    elif today > cuota.fecha_vencimiento:
                        cuota.estado_calculado = "Vencida"
                        cuota.badge_color = "bg-rose-100 text-rose-800 border-rose-200"
                    else:
                        cuota.estado_calculado = "Al Día"
                        cuota.badge_color = "bg-blue-100 text-blue-800 border-blue-200"
                    
                    cuota.saldo_restante = max(0, cuota.monto - cuota.monto_abonado)
            except Exception:
                deuda = None
                cuotas = []

            context.update({
                'deuda': deuda,
                'cuotas': cuotas,
            })

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
