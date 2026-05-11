from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView, ListView, View
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone

from ..models.simulacros import (
    Simulacro, VentanaSimulacro, IntentoSimulacro, IntentoSesion,
    RespuestaSimulacro, calcular_puntaje_global
)
from ..models.banco import Opcion
from ..forms import SimulacroForm, VentanaSimulacroForm
from curriculo.views.mixins import HistorialMixin


# --- Permisos y Mixins ---

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class SimulacroAccessMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.role == 'virtual_student' or user.is_staff)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta área. Los simulacros son exclusivos para estudiantes virtuales.")
        return redirect('curriculo:programa_list')


# --- CRUD Básico Simulacro ---

class SimulacroCreateView(LoginRequiredMixin, StaffRequiredMixin, HistorialMixin, CreateView):
    model = Simulacro
    form_class = SimulacroForm
    template_name = 'evaluaciones/simulacro_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        modulo_id = self.request.GET.get('modulo')
        if modulo_id:
            initial['modulo'] = modulo_id
        return initial

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

class SimulacroUpdateView(LoginRequiredMixin, StaffRequiredMixin, HistorialMixin, UpdateView):
    model = Simulacro
    form_class = SimulacroForm
    template_name = 'evaluaciones/simulacro_form.html'
    
    def get_success_url(self):
        return reverse_lazy('evaluaciones:simulacro_detail', kwargs={'pk': self.object.pk})


# --- Gestión de Ventanas ---

class VentanaSimulacroCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = VentanaSimulacro
    form_class = VentanaSimulacroForm
    template_name = 'evaluaciones/ventana_simulacro_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.simulacro = get_object_or_404(Simulacro, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.simulacro = self.simulacro
        form.instance.creador = self.request.user
        messages.success(self.request, "Ventana de simulacro creada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['simulacro'] = self.simulacro
        return context

    def get_success_url(self):
        return reverse_lazy('evaluaciones:simulacro_detail', kwargs={'pk': self.simulacro.pk})


# --- Listado y Detalle (Visualización) ---

class SimulacroListView(LoginRequiredMixin, SimulacroAccessMixin, ListView):
    model = Simulacro
    template_name = 'evaluaciones/simulacro_list.html'
    context_object_name = 'simulacros'
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset().select_related('modulo', 'creador').order_by('orden')
        
        # Filtro de búsqueda
        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(titulo__icontains=q)
            
        # Filtro de visibilidad según rol
        if not self.request.user.is_staff:
            # Los estudiantes solo ven los que están publicados
            qs = qs.filter(estado='publicado')
            
            # Y solo aquellos que tienen una ventana activa AHORA (o si ya tienen un intento)
            # Para simplificar, obtenemos los PK de simulacros disponibles o que el usuario ya ha intentado
            ahora = timezone.now()
            ids_con_ventana = VentanaSimulacro.objects.filter(
                fecha_apertura__lte=ahora, fecha_cierre__gte=ahora
            ).values_list('simulacro_id', flat=True)
            
            ids_intentados = IntentoSimulacro.objects.filter(
                usuario=self.request.user
            ).values_list('simulacro_id', flat=True)
            
            qs = qs.filter(id__in=list(ids_con_ventana) + list(ids_intentados))
            
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q_val'] = self.request.GET.get('q', '')
        return context


class SimulacroDetailView(LoginRequiredMixin, SimulacroAccessMixin, DetailView):
    model = Simulacro
    template_name = 'evaluaciones/simulacro_detail.html'
    context_object_name = 'simulacro'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        simulacro = self.object
        
        # Obtener ventana activa y el intento del usuario (si existe)
        context['ventana_activa'] = simulacro.ventana_activa()
        
        # Verificamos si el usuario ya tiene un intento
        intento = IntentoSimulacro.objects.filter(
            usuario=self.request.user, simulacro=simulacro
        ).first()
        context['intento_usuario'] = intento
        
        # Si es staff, pasamos todas las ventanas para listarlas
        if self.request.user.is_staff:
            context['ventanas'] = simulacro.ventanas.all()
            
        return context


# --- Realización del Simulacro ---

class SimulacroResolverView(LoginRequiredMixin, SimulacroAccessMixin, DetailView):
    model = Simulacro
    template_name = 'evaluaciones/simulacro_resolver.html'
    context_object_name = 'simulacro'

    def dispatch(self, request, *args, **kwargs):
        simulacro = self.get_object()
        
        # Verificar si está disponible (ventana activa + publicado)
        ventana_activa = simulacro.ventana_activa()
        if not request.user.is_staff and not ventana_activa:
            messages.error(request, "Este simulacro no se encuentra disponible actualmente.")
            return redirect('evaluaciones:simulacro_detail', pk=simulacro.pk)

        # Buscar si hay un intento en curso o finalizado
        intento = IntentoSimulacro.objects.filter(usuario=request.user, simulacro=simulacro).first()
        
        if intento and intento.fecha_fin:
            # Ya lo finalizó
            messages.info(request, "Ya has completado este simulacro.")
            return redirect('evaluaciones:simulacro_resultado', pk=intento.pk)
            
        if not intento:
            # Crear el intento inicial
            intento = IntentoSimulacro.objects.create(
                usuario=request.user,
                simulacro=simulacro,
                ventana=ventana_activa
            )

        self.intento = intento
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        simulacro = self.object
        
        # Lógica de sesiones: buscamos la primera sesión no finalizada
        sesiones_ordenadas = simulacro.sesiones.all().order_by('orden')
        sesion_actual = None
        intento_sesion_actual = None
        
        for sesion in sesiones_ordenadas:
            int_ses, created = IntentoSesion.objects.get_or_create(
                intento_simulacro=self.intento,
                sesion=sesion
            )
            if not int_ses.fecha_fin:
                sesion_actual = sesion
                intento_sesion_actual = int_ses
                break
                
        if not sesion_actual:
            # Si no hay sesión actual, es que terminó todas las sesiones
            # Finalizar el intento simulacro global
            return redirect('evaluaciones:simulacro_enviar', pk=simulacro.pk)

        context['intento'] = self.intento
        context['sesion_actual'] = sesion_actual
        context['intento_sesion_actual'] = intento_sesion_actual
        context['duracion_minutos'] = simulacro.duracion_minutos
        
        # Estructurar las preguntas de la sesión actual
        preguntas_por_componente = []
        for comp in sesion_actual.componentes.all().order_by('orden'):
            preguntas = comp.preguntas_componente.select_related(
                'pregunta', 'pregunta__bloque_contexto'
            ).prefetch_related('pregunta__opciones').order_by('orden')
            
            if preguntas.exists():
                preguntas_por_componente.append({
                    'componente': comp,
                    'preguntas': preguntas
                })
                
        context['preguntas_por_componente'] = preguntas_por_componente
        
        # Para el frontend
        tiempo_transcurrido = (timezone.now() - intento_sesion_actual.fecha_inicio).total_seconds()
        tiempo_restante_segundos = max(0, (simulacro.duracion_minutos * 60) - tiempo_transcurrido)
        context['tiempo_restante_segundos'] = tiempo_restante_segundos

        return context


class SimulacroEnviarView(LoginRequiredMixin, SimulacroAccessMixin, View):
    """
    Recibe el POST cuando se envía una sesión del simulacro.
    Si es la última sesión, calcula el puntaje global y cierra el simulacro.
    """
    def post(self, request, pk):
        simulacro = get_object_or_404(Simulacro, pk=pk)
        intento = get_object_or_404(IntentoSimulacro, usuario=request.user, simulacro=simulacro)
        
        if intento.fecha_fin:
            return redirect('evaluaciones:simulacro_resultado', pk=intento.pk)

        # Determinar qué sesión se está enviando
        sesion_id = request.POST.get('sesion_id')
        if not sesion_id:
            messages.error(request, "Error: No se identificó la sesión.")
            return redirect('evaluaciones:simulacro_resolver', pk=simulacro.pk)

        int_ses = get_object_or_404(IntentoSesion, id=sesion_id, intento_simulacro=intento)
        
        # Si ya había terminado esta sesión, ignorar y seguir a la siguiente
        if not int_ses.fecha_fin:
            # Procesar respuestas
            # El form enviará datos en formato `pregunta_{id}`
            preguntas_sesion = []
            for comp in int_ses.sesion.componentes.all():
                for p in comp.preguntas_componente.all():
                    preguntas_sesion.append(p.pregunta)

            for pregunta in preguntas_sesion:
                opcion_id = request.POST.get(f'pregunta_{pregunta.id}')
                if opcion_id:
                    try:
                        opcion_obj = Opcion.objects.get(id=opcion_id, pregunta=pregunta)
                        RespuestaSimulacro.objects.create(
                            intento_sesion=int_ses,
                            pregunta=pregunta,
                            opcion_seleccionada=opcion_obj,
                            es_correcta=opcion_obj.es_correcta
                        )
                    except Opcion.DoesNotExist:
                        pass
                else:
                    # Registramos que no la respondió, pero sin opción
                    RespuestaSimulacro.objects.create(
                        intento_sesion=int_ses,
                        pregunta=pregunta,
                        opcion_seleccionada=None,
                        es_correcta=False
                    )

            # Finalizar sesión
            int_ses.fecha_fin = timezone.now()
            int_ses.save()

        # Comprobar si hay más sesiones pendientes
        sesiones_pendientes = False
        for s in simulacro.sesiones.all().order_by('orden'):
            is_ses = IntentoSesion.objects.filter(intento_simulacro=intento, sesion=s).first()
            if not is_ses or not is_ses.fecha_fin:
                sesiones_pendientes = True
                break

        if sesiones_pendientes:
            messages.success(request, f"Sesión '{int_ses.sesion.nombre}' enviada. Puedes continuar con la siguiente.")
            return redirect('evaluaciones:simulacro_resolver', pk=simulacro.pk)
        else:
            # Terminar el simulacro completo
            self.finalizar_simulacro(intento)
            messages.success(request, "¡Felicitaciones! Has completado el simulacro.")
            return redirect('evaluaciones:simulacro_resultado', pk=intento.pk)

    def finalizar_simulacro(self, intento):
        """Calcula los puntajes y cierra el intento global"""
        simulacro = intento.simulacro
        intento.fecha_fin = timezone.now()
        
        # Calcular tiempo empleado sumando las sesiones
        total_minutos = sum(
            [ses.get_tiempo_empleado_minutos() for ses in intento.intentos_sesion.all() if ses.get_tiempo_empleado_minutos()]
        )
        intento.tiempo_empleado_minutos = int(total_minutos)
        
        # Calcular puntaje por componentes agrupados por materia
        materias_stats = {}
        
        todas_las_respuestas = RespuestaSimulacro.objects.filter(intento_sesion__intento_simulacro=intento)
        
        for sesion in simulacro.sesiones.all():
            for comp in sesion.componentes.all():
                materia_nombre = comp.componente.nombre
                if materia_nombre not in materias_stats:
                    materias_stats[materia_nombre] = {'correctas': 0, 'total': 0}
                    
                preg_ids = comp.preguntas_componente.values_list('pregunta_id', flat=True)
                respuestas_comp = todas_las_respuestas.filter(pregunta_id__in=preg_ids)
                
                materias_stats[materia_nombre]['total'] += respuestas_comp.count()
                materias_stats[materia_nombre]['correctas'] += respuestas_comp.filter(es_correcta=True).count()

        resultados_componentes = []
        for nombre, stats in materias_stats.items():
            total = stats['total']
            correctas = stats['correctas']
            pct = (correctas / total * 100) if total > 0 else 0
            
            resultados_componentes.append({
                'materia_nombre': nombre,
                'correctas': correctas,
                'total': total,
                'porcentaje': round(pct, 2)
            })

        intento.resultados_detallados = resultados_componentes
        intento.puntaje_global = calcular_puntaje_global(resultados_componentes)
        intento.save()


class SimulacroResultadoView(LoginRequiredMixin, SimulacroAccessMixin, DetailView):
    model = IntentoSimulacro
    template_name = 'evaluaciones/simulacro_resultado.html'
    context_object_name = 'intento'

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(usuario=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        intento = self.object
        
        # Desglose de respuestas por sesión
        # Por simplicidad, podríamos mostrar la gráfica o la tabla directamente.
        # context['detalles'] = intento.resultados_detallados
        
        return context
