import re
from django.views.generic import View
from django.shortcuts import render
from django.db.models import Avg, Q
from django.utils import timezone

from academico.models import Alumno, Asistencia, Nota, Inasistencia
from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
from cartera.models import Deuda, Cuota
from cartera.utils import evaluar_bloqueo_cartera
from evaluaciones.models.simulacros import IntentoSimulacro
from evaluaciones.models.talleres import IntentoTaller
from usuarios.models import User


class VirtualStudentWrapper:
    """
    Envoltura para estudiantes 100% virtuales o usuarios tipo Student/VirtualStudent
    que no cuenten con un registro previo en la tabla Alumno.
    """
    def __init__(self, user):
        self.user = user
        self.usuario = user
        self.nombres = user.first_name or user.username
        self.primer_apellido = user.last_name or ""
        self.segundo_apellido = ""
        self.identificacion = user.numero_documento or user.username
        self.tipo_identificacion = user.tipo_documento or "CC"
        self.es_becado = False
        self.estado = "activo" if user.is_active else "inactivo"
        self.grupo_actual = None
        self.municipio = user.municipio
        self.es_virtual = True

    def get_estado_display(self):
        return "Activo" if self.user.is_active else "Inactivo"

    def get_tipo_programa_display(self):
        return "100% Virtual"


class ConsultaEstudianteView(View):
    template_name = 'academico/consulta_estudiante.html'

    def get(self, request, *args, **kwargs):
        identificacion = request.GET.get('identificacion', '').strip()

        # Si no se pasó en GET, pero el usuario logueado es estudiante o virtual student
        if not identificacion and request.user.is_authenticated:
            if hasattr(request.user, 'perfil_alumno') and request.user.perfil_alumno:
                identificacion = request.user.perfil_alumno.identificacion
            elif request.user.numero_documento:
                identificacion = request.user.numero_documento
            elif any(g.name in ['Student', 'VirtualStudent'] for g in request.user.groups.all()):
                identificacion = request.user.username

        context = {
            'identificacion': identificacion,
            'alumno': None,
            'busqueda_realizada': False,
            'error_mensaje': None,
        }

        if identificacion:
            context['busqueda_realizada'] = True
            clean_id = re.sub(r'[^0-9a-zA-Z]', '', identificacion)

            # 1. Buscar en Alumno
            alumno = Alumno.objects.filter(
                Q(identificacion__iexact=identificacion) | Q(identificacion__iexact=clean_id)
            ).select_related(
                'municipio', 
                'municipio__departamento', 
                'grupo_actual', 
                'grupo_actual__salon', 
                'grupo_actual__salon__sede',
                'usuario'
            ).first()

            # 2. Si no se encontró en Alumno, buscar en User (VirtualStudent o Student sin perfil Alumno)
            if not alumno:
                user_match = User.objects.filter(
                    Q(numero_documento__iexact=identificacion) |
                    Q(numero_documento__iexact=clean_id) |
                    Q(username__iexact=identificacion) |
                    Q(username__iexact=clean_id)
                ).select_related('municipio', 'municipio__departamento').first()

                if user_match:
                    if hasattr(user_match, 'perfil_alumno') and user_match.perfil_alumno:
                        alumno = user_match.perfil_alumno
                    else:
                        if user_match.numero_documento:
                            alumno = Alumno.objects.filter(identificacion__iexact=user_match.numero_documento).first()
                        if not alumno:
                            alumno = VirtualStudentWrapper(user_match)

            if not alumno:
                context['error_mensaje'] = f"No se encontró ningún estudiante con el número de documento '{identificacion}'."
                return render(request, self.template_name, context)

            context['alumno'] = alumno

            # Identificar usuario para actividades digitales (talleres y simulacros virtuales)
            usuario_actividades = None
            if hasattr(alumno, 'usuario') and alumno.usuario:
                usuario_actividades = alumno.usuario
            elif hasattr(alumno, 'user') and alumno.user:
                usuario_actividades = alumno.user
            elif hasattr(alumno, 'identificacion'):
                usuario_actividades = User.objects.filter(
                    Q(numero_documento__iexact=alumno.identificacion) |
                    Q(numero_documento__iexact=clean_id)
                ).first()

            # Determinar tipo de estudiante según grupos de permisos o pertenencia a grupo físico
            es_virtual = False
            es_presencial = False

            if usuario_actividades:
                grupos = set(usuario_actividades.groups.values_list('name', flat=True))
                if 'VirtualStudent' in grupos and 'Student' not in grupos:
                    es_virtual = True
                elif 'Student' in grupos and 'VirtualStudent' not in grupos:
                    es_presencial = True
                elif 'VirtualStudent' in grupos and 'Student' in grupos:
                    if isinstance(alumno, Alumno) and alumno.grupo_actual_id:
                        es_presencial = True
                    else:
                        es_virtual = True

            if not es_virtual and not es_presencial:
                if isinstance(alumno, Alumno) and alumno.grupo_actual_id:
                    es_presencial = True
                else:
                    es_virtual = True

            # 1. Clases Presenciales (Unificar Asistencias y Notas por medio del objeto Clase)
            clases_historial = []
            total_asistencias = 0
            asistencias_presente = 0
            asistencias_faltas = 0
            porcentaje_asistencia = 0
            promedios_materias = []
            simulacros_fisicos = []
            simulacros_diagnosticos = []

            if isinstance(alumno, Alumno):
                asistencias_dict = {
                    a.clase_id: a
                    for a in Asistencia.objects.filter(alumno=alumno).select_related('clase', 'clase__materia', 'clase__profesor')
                }
                notas_dict = {
                    n.clase_id: n
                    for n in Nota.objects.filter(alumno=alumno).select_related('clase', 'clase__materia', 'clase__profesor')
                }
                inasistencias_dict = {
                    i.clase_id: i
                    for i in Inasistencia.objects.filter(alumno=alumno)
                }

                all_clase_ids = set(asistencias_dict.keys()) | set(notas_dict.keys())

                for cid in all_clase_ids:
                    a_obj = asistencias_dict.get(cid)
                    n_obj = notas_dict.get(cid)
                    i_obj = inasistencias_dict.get(cid)

                    clase = a_obj.clase if a_obj else n_obj.clase
                    asistio = a_obj.asistio if a_obj else False
                    tiene_asistencia = a_obj is not None

                    tiene_justificacion = False
                    motivo_justificacion = ""
                    if not asistio and i_obj and i_obj.justificada:
                        tiene_justificacion = True
                        motivo_justificacion = i_obj.motivo or "Inasistencia justificada"

                    nota_valor = n_obj.nota if n_obj else None

                    clases_historial.append({
                        'clase': clase,
                        'materia': clase.materia,
                        'profesor': clase.profesor,
                        'fecha': clase.fecha,
                        'tiene_asistencia': tiene_asistencia,
                        'asistio': asistio,
                        'tiene_justificacion': tiene_justificacion,
                        'motivo_justificacion': motivo_justificacion,
                        'nota': nota_valor,
                    })

                clases_historial.sort(key=lambda x: x['fecha'], reverse=True)

                total_asistencias = sum(1 for c in clases_historial if c['tiene_asistencia'])
                asistencias_presente = sum(1 for c in clases_historial if c['asistio'])
                asistencias_faltas = sum(1 for c in clases_historial if c['tiene_asistencia'] and not c['asistio'])
                porcentaje_asistencia = round((asistencias_presente / total_asistencias * 100), 1) if total_asistencias > 0 else 0

                promedios_materias = Nota.objects.filter(
                    alumno=alumno,
                    clase__estado='vista'
                ).values('clase__materia__nombre').annotate(
                    promedio=Avg('nota')
                ).order_by('clase__materia__nombre')

                simulacros_fisicos = alumno.resultados_simulacros.select_related(
                    'simulacro'
                ).order_by('-fecha_realizacion')

                simulacros_diagnosticos = alumno.resultados_simulacros_diagnosticos.select_related(
                    'simulacro'
                ).order_by('-fecha_realizacion')

            # 2. Simulacros Virtuales y Talleres Virtuales (PreICFES Virtual)
            simulacros_virtuales = []
            intentos_talleres = []
            if usuario_actividades:
                simulacros_virtuales = list(IntentoSimulacro.objects.filter(
                    usuario=usuario_actividades,
                    fecha_fin__isnull=False
                ).select_related('simulacro').order_by('-fecha_fin'))

                intentos_talleres = list(IntentoTaller.objects.filter(
                    usuario=usuario_actividades,
                    fecha_fin__isnull=False
                ).select_related('taller', 'taller__modulo', 'taller__tema', 'clase', 'clase__materia').order_by('-fecha_fin'))

            # 3. Cartera y Cuotas (Lógica unificada desde cartera.utils)
            bloqueo_info = evaluar_bloqueo_cartera(
                alumno=alumno if isinstance(alumno, Alumno) else None,
                user=usuario_actividades,
                identificacion=getattr(alumno, 'identificacion', None) or identificacion,
            )
            deuda = bloqueo_info['deuda']
            cuotas = bloqueo_info['cuotas']
            total_abonado = bloqueo_info['total_abonado']
            tiene_cuotas_vencidas = bloqueo_info['tiene_cuotas_vencidas']
            bloquear_simulacros_por_cartera = bloqueo_info['bloquear']
            motivo_bloqueo_simulacros = bloqueo_info['motivo']
            cuotas_afectadas_simulacros = bloqueo_info['cuotas_afectadas']
            suma_montos_pagadas_o_parciales = bloqueo_info['suma_montos_pagadas_o_parciales']
            suma_abonados_pagadas_o_parciales = bloqueo_info['suma_abonados_pagadas_o_parciales']

            total_simulacros_evaluados = 0
            if es_presencial:
                total_simulacros_evaluados = (
                    (simulacros_fisicos.count() if simulacros_fisicos else 0) +
                    (simulacros_diagnosticos.count() if simulacros_diagnosticos else 0)
                )
            else:
                total_simulacros_evaluados = len(simulacros_virtuales)

            context.update({
                'es_presencial': es_presencial,
                'es_virtual': es_virtual,
                'clases_historial': clases_historial,
                'total_asistencias': total_asistencias,
                'asistencias_presente': asistencias_presente,
                'asistencias_faltas': asistencias_faltas,
                'porcentaje_asistencia': porcentaje_asistencia,
                'promedios_materias': promedios_materias,
                'simulacros_fisicos': simulacros_fisicos,
                'simulacros_diagnosticos': simulacros_diagnosticos,
                'simulacros_virtuales': simulacros_virtuales,
                'intentos_talleres': intentos_talleres,
                'deuda': deuda,
                'cuotas': cuotas,
                'total_abonado': total_abonado,
                'tiene_cuotas_vencidas': tiene_cuotas_vencidas,
                'bloquear_simulacros_por_cartera': bloquear_simulacros_por_cartera,
                'motivo_bloqueo_simulacros': motivo_bloqueo_simulacros,
                'cuotas_afectadas_simulacros': cuotas_afectadas_simulacros,
                'total_simulacros_evaluados': total_simulacros_evaluados,
                'suma_montos_pagadas_o_parciales': suma_montos_pagadas_o_parciales,
                'suma_abonados_pagadas_o_parciales': suma_abonados_pagadas_o_parciales,
            })

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
