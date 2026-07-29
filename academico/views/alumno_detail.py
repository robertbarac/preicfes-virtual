from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.utils import timezone
import json
from django.template.loader import render_to_string

from academico.models import Alumno, Asistencia, Nota, Inasistencia
from cartera.models import Deuda, AcuerdoPago

class AlumnoDetailView(LoginRequiredMixin, DetailView):
    model = Alumno
    template_name = 'academico/alumno_detail.html'
    context_object_name = 'alumno'

    def get_queryset(self):
        """Filtra el queryset según el rol del usuario (mismo criterio que AlumnosListView)."""
        qs = super().get_queryset().select_related('grupo_actual__salon__sede')
        user = self.request.user

        if user.is_superuser:
            return qs
        elif user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            if hasattr(user, 'departamento') and user.departamento:
                return qs.filter(municipio__departamento=user.departamento)
        elif getattr(user, 'is_observador', False):
            if hasattr(user, 'sede') and user.sede:
                return qs.filter(grupo_actual__salon__sede=user.sede)
            return qs.none()
        else:
            # Staff general: filtrar por municipio
            if hasattr(user, 'municipio') and user.municipio:
                return qs.filter(municipio=user.municipio)
            return qs.none()
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        alumno = self.get_object()
        user = self.request.user

        # Flags de permisos para simplificar la lógica en la plantilla
        can_view_academic = user.is_superuser or user.groups.filter(name__in=['SecretariaAcademica', 'CoordinadorDepartamental', 'Auxiliar', 'ObservadorColegio']).exists()
        can_view_cartera = user.is_superuser or user.groups.filter(name__in=['SecretariaCartera', 'CoordinadorDepartamental', 'Auxiliar', 'ObservadorColegio']).exists()

        # Flags de permisos específicos para acciones
        context['can_add_cuota'] = user.has_perm('cartera.add_cuota')
        context['can_change_deuda'] = user.has_perm('cartera.change_deuda')
        context['is_manager'] = user.is_superuser or user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()

        context['can_view_academic_history'] = can_view_academic
        context['can_view_cartera_info'] = can_view_cartera
        

        # Obtener estadísticas de asistencia
        asistencias = Asistencia.objects.filter(alumno=alumno)
        
        # Obtener diccionario de inasistencias para mapear/justificar
        inasistencias_justificadas = {
            inasistencia.clase.id: inasistencia
            for inasistencia in Inasistencia.objects.filter(alumno=alumno)
        }
        
        # Convertir a lista optimizada y precalcular enlaces de WhatsApp
        asistencias_vistas = list(asistencias.order_by('-clase__fecha').select_related('clase', 'clase__materia'))
        for asistencia in asistencias_vistas:
            if not asistencia.asistio:
                # Se considera justificada si el registro de inasistencia existe y está marcado como justificada=True
                inasistencia_obj = inasistencias_justificadas.get(asistencia.clase.id)
                asistencia.tiene_justificacion = inasistencia_obj is not None and inasistencia_obj.justificada
                
                if not asistencia.tiene_justificacion:
                    # Validar números de teléfono de padres
                    celular_padre = alumno.celular_padre.strip() if alumno.celular_padre else ''
                    celular_madre = alumno.celular_madre.strip() if alumno.celular_madre else ''
                    
                    asistencia.celular_padre = celular_padre if (celular_padre and celular_padre != 'SIN DATOS') else None
                    asistencia.celular_madre = celular_madre if (celular_madre and celular_madre != 'SIN DATOS') else None
                    
                    if asistencia.celular_padre or asistencia.celular_madre:
                        estudiante_nombre = f"{alumno.nombres} {alumno.primer_apellido}"
                        if alumno.segundo_apellido:
                            estudiante_nombre += f" {alumno.segundo_apellido}"
                        
                        clase_fecha = asistencia.clase.fecha.strftime('%d/%m/%Y') if hasattr(asistencia.clase.fecha, 'strftime') else str(asistencia.clase.fecha)
                        
                        base_context = {
                            'estudiante_nombre': estudiante_nombre,
                            'materia': asistencia.clase.materia.nombre,
                            'fecha': clase_fecha,
                            'horario': asistencia.clase.get_horario_display(),
                        }
                        
                        if asistencia.celular_padre:
                            padre_nombre = f"{alumno.nombres_padre} {alumno.primer_apellido_padre}".strip()
                            if not padre_nombre or 'SIN DATOS' in padre_nombre:
                                padre_nombre = "Padre de familia"
                            
                            ctx = base_context.copy()
                            ctx['nombre_acudiente'] = padre_nombre
                            asistencia.whatsapp_padre_message = render_to_string(
                                'academico/inasistencia_whatsapp_template.txt',
                                ctx
                            ).replace('\n', '%0A').replace(' ', '%20')
                            
                        if asistencia.celular_madre:
                            madre_nombre = f"{alumno.nombres_madre} {alumno.primer_apellido_madre}".strip()
                            if not madre_nombre or 'SIN DATOS' in madre_nombre:
                                madre_nombre = "Madre de familia"
                            
                            ctx = base_context.copy()
                            ctx['nombre_acudiente'] = madre_nombre
                            asistencia.whatsapp_madre_message = render_to_string(
                                'academico/inasistencia_whatsapp_template.txt',
                                ctx
                            ).replace('\n', '%0A').replace(' ', '%20')
        
        # Obtener cuotas
        try:
            deuda = alumno.deuda
            cuotas = deuda.cuotas.all().order_by('fecha_vencimiento')
            
            # Agregar mensaje WhatsApp a cada cuota
            for cuota in cuotas:
                # Forzar la actualización del estado de la cuota según la fecha actual
                if cuota.monto_abonado >= cuota.monto:
                    cuota.estado = "pagada"
                elif cuota.monto_abonado > 0:
                    cuota.estado = "pagada_parcial"
                elif timezone.localtime(timezone.now()).date() > cuota.fecha_vencimiento:
                    cuota.estado = "vencida"
                else:
                    cuota.estado = "emitida"
                
                alumno = cuota.deuda.alumno
                
                # Generar mensaje diferente según el estado de la cuota
                if cuota.estado == "emitida":
                    # Para cuotas emitidas (próximos pagos): calcular días restantes
                    cuota.dias_restantes = (cuota.fecha_vencimiento - timezone.localtime(timezone.now()).date()).days
                    
                    # Renderizar el mensaje con los datos actuales
                    message_context = {
                        'nombres': alumno.nombres,
                        'primer_apellido': alumno.primer_apellido,
                        'segundo_apellido': alumno.segundo_apellido,
                        'fecha_vencimiento': cuota.fecha_vencimiento,
                        'dias_restantes': cuota.dias_restantes,
                        'monto': cuota.monto
                    }
                    
                    # Renderizar el template y codificar para URL
                    cuota.whatsapp_message = render_to_string(
                        'cartera/proximo_pago_template.txt',
                        message_context
                    ).replace('\n', '%0A').replace(' ', '%20')
                
                elif cuota.estado == "vencida":
                    # Para cuotas vencidas: calcular días de atraso
                    cuota.dias_atraso = (timezone.localtime(timezone.now()).date() - cuota.fecha_vencimiento).days
                    
                    # Renderizar el mensaje con los datos actuales
                    message_context = {
                        'nombres': alumno.nombres,
                        'primer_apellido': alumno.primer_apellido,
                        'segundo_apellido': alumno.segundo_apellido,
                        'fecha_vencimiento': cuota.fecha_vencimiento,
                        'dias_atraso': cuota.dias_atraso,
                        'monto': cuota.monto,
                        'monto_abonado': cuota.monto_abonado,
                        'saldo_pendiente': cuota.deuda.saldo_pendiente
                    }
                    
                    # Renderizar el template y codificar para URL
                    cuota.whatsapp_message = render_to_string(
                        'cartera/whatsapp_message_template.txt',
                        message_context
                    ).replace('\n', '%0A').replace(' ', '%20')
            # Preparar datos de acuerdos para JSON
            acuerdos_data = {}
            for cuota in cuotas:
                acuerdos = cuota.acuerdos.all().order_by('-fecha_acuerdo')
                acuerdos_data[cuota.id] = [
                    {
                        'fecha_acuerdo': a.fecha_acuerdo.strftime('%d/%m/%Y'),
                        'fecha_prometida_pago': a.fecha_prometida_pago.strftime('%d/%m/%Y'),
                        'nota': a.nota,
                        'estado': a.get_estado_display(),
                    }
                    for a in acuerdos
                ]

        except Deuda.DoesNotExist:
            deuda = None
            cuotas = []
            acuerdos_data = {}

        context.update({
            'acuerdos_json': json.dumps(acuerdos_data),
            'titulo': f'Detalles de {alumno}',
            'deuda': deuda,
            'saldo_pendiente': deuda.saldo_pendiente if deuda else 0,
            'estado_deuda': deuda.estado if deuda else 'Sin deuda',
            'cuotas': cuotas,
            'asistencias': asistencias_vistas,
            'total_asistencias': len(asistencias_vistas),
            'asistencias_presente': sum(1 for a in asistencias_vistas if a.asistio),
            'asistencias_faltas': sum(1 for a in asistencias_vistas if not a.asistio),
            
            # Obtener notas y promedios por materia
            'notas': Nota.objects.filter(alumno=alumno, clase__estado='vista'),
            'promedios_materias': Nota.objects.filter(
                alumno=alumno,
                clase__estado='vista'
            ).values('clase__materia__nombre').annotate(
                promedio=Avg('nota')
            ).order_by('clase__materia__nombre'),

            # Crear un diccionario para mapear inasistencias a clases
            'inasistencias_justificadas': inasistencias_justificadas,
            
            # Resultados de Simulacros
            'resultados_simulacros': alumno.resultados_simulacros.select_related('simulacro', 'registrador').order_by('-fecha_realizacion'),
        })
        
        return context
