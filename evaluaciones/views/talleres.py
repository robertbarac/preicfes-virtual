from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView
from ..models.talleres import Taller
from ..forms import TallerForm
from curriculo.views.mixins import HistorialMixin

class TallerCreateView(HistorialMixin, CreateView):
    model = Taller
    form_class = TallerForm
    template_name = 'evaluaciones/taller_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        modulo_id = self.request.GET.get('modulo')
        if modulo_id:
            initial['modulo'] = modulo_id
        return initial

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

class TallerUpdateView(HistorialMixin, UpdateView):
    model = Taller
    form_class = TallerForm
    template_name = 'evaluaciones/taller_form.html'
    
    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

class TallerDetailView(DetailView):
    model = Taller
    template_name = 'evaluaciones/taller_detail.html'
    context_object_name = 'taller'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            from ..models.talleres import IntentoTaller
            intentos = IntentoTaller.objects.filter(
                taller=self.object, 
                usuario=self.request.user
            ).order_by('-fecha_fin', '-fecha_inicio')
            context['intentos'] = intentos
            context['puede_intentar'] = intentos.count() < self.object.intentos_permitidos
        else:
            context['intentos'] = []
            context['puede_intentar'] = False
        return context

from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.views.generic import TemplateView
from ..models.banco import Pregunta

class TallerPreguntaManageView(TemplateView):
    template_name = 'evaluaciones/taller_preguntas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taller = get_object_or_404(Taller, pk=self.kwargs['pk'])
        context['taller'] = taller
        
        # Preguntas ya asignadas
        asignadas_ids = taller.preguntas_taller.values_list('pregunta_id', flat=True)
        context['preguntas_asignadas'] = taller.preguntas_taller.select_related('pregunta').all()
        
        # Filtros del buscador
        q = self.request.GET.get('q', '')
        tema_id = self.request.GET.get('tema', '')
        
        # Preguntas disponibles en el banco (podemos filtrar por tema del taller si es necesario)
        disponibles = Pregunta.objects.exclude(id__in=asignadas_ids).select_related('tema', 'tema__materia')
        
        if q:
            disponibles = disponibles.filter(enunciado__icontains=q)
            
        if tema_id:
            disponibles = disponibles.filter(tema_id=tema_id)
        elif taller.tema and not self.request.GET:
            # Si entramos por primera vez sin filtros explícitos, sugerimos las del tema del taller
            disponibles = disponibles.filter(tema=taller.tema)
            
        context['preguntas_disponibles'] = disponibles
        context['q_val'] = q
        context['tema_val'] = tema_id
        
        from curriculo.models.core import Tema
        context['temas_filtro'] = Tema.objects.select_related('materia').all()
        
        return context

    def post(self, request, *args, **kwargs):
        taller = get_object_or_404(Taller, pk=self.kwargs['pk'])
        action = request.POST.get('action')
        pregunta_id = request.POST.get('pregunta_id')
        
        if not pregunta_id:
            return redirect('evaluaciones:taller_preguntas_manage', pk=taller.pk)
            
        pregunta = get_object_or_404(Pregunta, pk=pregunta_id)
        from ..models.talleres import PreguntaTaller
        
        if action == 'add':
            # Verificar si ya existe para no duplicar
            if not PreguntaTaller.objects.filter(taller=taller, pregunta=pregunta).exists():
                # Asignar un orden base (al final)
                ultimo_orden = PreguntaTaller.objects.filter(taller=taller).order_by('-orden').first()
                nuevo_orden = ultimo_orden.orden + 1 if ultimo_orden else 1
                PreguntaTaller.objects.create(taller=taller, pregunta=pregunta, orden=nuevo_orden)
                messages.success(request, f"Pregunta '{pregunta.enunciado[:30]}...' añadida al taller.")
        
        elif action == 'remove':
            relacion = PreguntaTaller.objects.filter(taller=taller, pregunta=pregunta).first()
            if relacion:
                relacion.delete()
                messages.warning(request, f"Pregunta removida del taller.")
                
        return redirect('evaluaciones:taller_preguntas_manage', pk=taller.pk)

from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models.talleres import IntentoTaller, RespuestaTaller
from ..models.banco import Opcion

class TallerResolverView(LoginRequiredMixin, TemplateView):
    template_name = 'evaluaciones/taller_resolver.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taller = get_object_or_404(Taller, pk=self.kwargs['pk'])
        context['taller'] = taller
        context['preguntas'] = taller.preguntas_taller.select_related('pregunta').all()
        
        # Verificar intentos previos
        intentos = IntentoTaller.objects.filter(usuario=self.request.user, taller=taller)
        context['intentos_realizados'] = intentos.count()
        context['puede_intentar'] = intentos.count() < taller.intentos_permitidos
        context['intentos'] = intentos.order_by('-fecha_inicio')
        
        return context

    def post(self, request, *args, **kwargs):
        taller = get_object_or_404(Taller, pk=self.kwargs['pk'])
        
        # Verificar si tiene intentos disponibles
        intentos_realizados = IntentoTaller.objects.filter(usuario=request.user, taller=taller).count()
        if intentos_realizados >= taller.intentos_permitidos:
            messages.error(request, "Ya has superado el límite de intentos permitidos para este taller.")
            return redirect('evaluaciones:taller_detail', pk=taller.pk)

        # Crear nuevo intento
        intento = IntentoTaller.objects.create(
            usuario=request.user,
            taller=taller
        )

        preguntas_taller = taller.preguntas_taller.select_related('pregunta').all()
        total_preguntas = preguntas_taller.count()
        respuestas_correctas = 0

        for pt in preguntas_taller:
            pregunta = pt.pregunta
            opcion_id = request.POST.get(f'pregunta_{pregunta.id}')
            
            if opcion_id:
                try:
                    opcion_seleccionada = Opcion.objects.get(id=opcion_id, pregunta=pregunta)
                    es_correcta = opcion_seleccionada.es_correcta
                    if es_correcta:
                        respuestas_correctas += 1
                        
                    RespuestaTaller.objects.create(
                        intento=intento,
                        pregunta=pregunta,
                        opcion_seleccionada=opcion_seleccionada,
                        es_correcta=es_correcta
                    )
                except Opcion.DoesNotExist:
                    pass

        # Calcular puntaje final
        if total_preguntas > 0:
            puntaje = (respuestas_correctas / total_preguntas) * 100
        else:
            puntaje = 0
            
        intento.puntaje_porcentaje = puntaje
        intento.fecha_fin = timezone.now()
        intento.save()

        messages.success(request, f"Taller completado. Tu puntaje fue: {puntaje:.2f}%")
        return redirect('evaluaciones:taller_detail', pk=taller.pk)

class TallerIntentoDetailView(LoginRequiredMixin, DetailView):
    model = IntentoTaller
    template_name = 'evaluaciones/taller_intento_detail.html'
    context_object_name = 'intento'

    def get_queryset(self):
        # Asegurarse de que el usuario solo pueda ver sus propios intentos (a menos que sea admin)
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(usuario=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        intento = self.object
        taller = intento.taller
        context['taller'] = taller
        
        # Recuperar todas las respuestas del intento
        respuestas_qs = intento.respuestas.select_related('pregunta', 'opcion_seleccionada').all()
        # Diccionario para acceder rápido a la respuesta dada por el ID de la pregunta
        respuestas_dict = {r.pregunta_id: r for r in respuestas_qs}
        
        # Opciones correctas pre-cargadas para evitar múltiples queries
        preguntas_ids = taller.preguntas_taller.values_list('pregunta_id', flat=True)
        opciones_correctas_qs = Opcion.objects.filter(
            pregunta_id__in=preguntas_ids, 
            es_correcta=True
        )
        opciones_correctas_dict = {oc.pregunta_id: oc for oc in opciones_correctas_qs}
        
        # Estructurar los datos para la plantilla
        detalles_preguntas = []
        preguntas_taller = taller.preguntas_taller.select_related('pregunta', 'pregunta__tema').prefetch_related('pregunta__opciones')
        
        for pt in preguntas_taller:
            pregunta = pt.pregunta
            respuesta_dada = respuestas_dict.get(pregunta.id)
            opcion_correcta = opciones_correctas_dict.get(pregunta.id)
            
            detalles_preguntas.append({
                'pregunta': pregunta,
                'opciones': pregunta.opciones.all(),
                'respuesta_dada': respuesta_dada,
                'opcion_correcta': opcion_correcta,
                'fue_correcta': respuesta_dada.es_correcta if respuesta_dada else False,
                'omitida': respuesta_dada is None
            })
            
        context['detalles_preguntas'] = detalles_preguntas
        return context

class TallerSolucionView(LoginRequiredMixin, DetailView):
    """
    Despliega la secuencia de respuestas correctas del Taller
    (Para uso de profesores o revisión general sin contexto de un intento específico)
    """
    model = Taller
    template_name = 'evaluaciones/taller_solucion.html'
    context_object_name = 'taller'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taller = self.object
        
        detalles_preguntas = []
        preguntas_taller = taller.preguntas_taller.select_related('pregunta', 'pregunta__tema').prefetch_related('pregunta__opciones').all()
        
        for pt in preguntas_taller:
            pregunta = pt.pregunta
            
            detalles_preguntas.append({
                'pregunta': pregunta,
                'opciones': pregunta.opciones.all(),
                'opcion_correcta': pregunta.opciones.filter(es_correcta=True).first(),
            })
            
        context['detalles_preguntas'] = detalles_preguntas
        return context

class TallerLecturaView(LoginRequiredMixin, DetailView):
    """
    Modo de Taller en lista (Lectura). 
    Muestra las preguntas pero NO permite enviar ni evalúa (no crea IntentoTaller).
    Ideal para perfiles futuros que solo pueden ver el contenido.
    """
    model = Taller
    template_name = 'evaluaciones/taller_lectura.html'
    context_object_name = 'taller'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taller = self.object
        context['preguntas'] = taller.preguntas_taller.select_related('pregunta', 'pregunta__tema').prefetch_related('pregunta__opciones').all()
        return context
