import re
from django.views.generic import View
from django.shortcuts import render
from django.db.models import Avg, Q
from django.utils import timezone

from academico.models import Alumno, Asistencia, Nota, Inasistencia
from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
from cartera.models import Deuda, Cuota
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

            # 3. Cartera y Cuotas (Solo visualización / Lectura)
            deuda = None
            cuotas = []
            total_abonado = 0
            tiene_cuotas_vencidas = False

            if isinstance(alumno, Alumno) and hasattr(alumno, 'deuda'):
                try:
                    deuda = alumno.deuda
                    cuotas = list(deuda.cuotas.all().order_by('fecha_vencimiento'))
                    today = timezone.localtime(timezone.now()).date()

                    for cuota in cuotas:
                        cuota.saldo_restante = max(0, cuota.monto - cuota.monto_abonado)

                        if cuota.estado == 'pagada' or cuota.monto_abonado >= cuota.monto:
                            cuota.estado_calculado = "Pagada"
                            cuota.badge_color = "bg-emerald-100 text-emerald-800 border-emerald-200"
                        elif cuota.estado == 'pagada_parcial' or cuota.monto_abonado > 0:
                            cuota.estado_calculado = "Pagada Parcial"
                            cuota.badge_color = "bg-amber-100 text-amber-800 border-amber-200"
                        elif cuota.estado == 'vencida' or today > cuota.fecha_vencimiento:
                            cuota.estado_calculado = "Vencida"
                            cuota.badge_color = "bg-rose-100 text-rose-800 border-rose-200"
                        else:
                            cuota.estado_calculado = "Al Día"
                            cuota.badge_color = "bg-blue-100 text-blue-800 border-blue-200"

                        # Se calcula sumando los montos abonados de las cuotas de su deuda, siempre que la cuota sea pagada o pagada parcial en su estado
                        if cuota.estado in ['pagada', 'pagada_parcial']:
                            total_abonado += cuota.monto_abonado

                    if total_abonado == 0 and deuda.valor_total and deuda.saldo_pendiente is not None:
                        total_abonado = max(0, deuda.valor_total - deuda.saldo_pendiente)

                    tiene_cuotas_vencidas = any(c.estado == 'vencida' or (today > c.fecha_vencimiento and c.saldo_restante > 0) for c in cuotas)
                except Exception:
                    deuda = None
                    cuotas = []
                    total_abonado = 0
                    tiene_cuotas_vencidas = False

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
            })

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
