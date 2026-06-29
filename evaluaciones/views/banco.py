from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, UpdateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models.banco import Pregunta, Opcion, ImagenPregunta
from django.db import models
from ..forms import PreguntaForm, OpcionFormSet, ImagenPreguntaFormSet
from curriculo.views.mixins import HistorialMixin

class PreguntaCreateView(HistorialMixin, CreateView):
    model = Pregunta
    form_class = PreguntaForm
    template_name = 'evaluaciones/pregunta_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['opciones'] = OpcionFormSet(self.request.POST, self.request.FILES)
            data['imagenes_pregunta'] = ImagenPreguntaFormSet(self.request.POST, self.request.FILES)
        else:
            data['opciones'] = OpcionFormSet()
            data['imagenes_pregunta'] = ImagenPreguntaFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        opciones = context['opciones']
        imagenes_pregunta = context['imagenes_pregunta']
        
        # Validamos los formsets ANTES de guardar la pregunta en base de datos
        if opciones.is_valid() and imagenes_pregunta.is_valid():
            from django.db import transaction
            with transaction.atomic():
                self.object = form.save()
                opciones.instance = self.object
                opciones.save()
                imagenes_pregunta.instance = self.object
                imagenes_pregunta.save()
            messages.success(self.request, "Pregunta guardada correctamente.")
        else:
            # Si hay errores de validación, volvemos a mostrar el formulario con los errores
            return self.render_to_response(self.get_context_data(form=form))
            
        # Refill back parameter or list
        taller_id = self.request.GET.get('taller')
        if taller_id:
            return redirect('evaluaciones:taller_preguntas_manage', pk=taller_id)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('evaluaciones:pregunta_list')

class PreguntaUpdateView(HistorialMixin, UpdateView):
    model = Pregunta
    form_class = PreguntaForm
    template_name = 'evaluaciones/pregunta_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['opciones'] = OpcionFormSet(self.request.POST, self.request.FILES, instance=self.object)
            data['imagenes_pregunta'] = ImagenPreguntaFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            data['opciones'] = OpcionFormSet(instance=self.object)
            data['imagenes_pregunta'] = ImagenPreguntaFormSet(instance=self.object)
        data['is_edit'] = True
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        opciones = context['opciones']
        imagenes_pregunta = context['imagenes_pregunta']

        # Validamos los formsets ANTES de guardar la pregunta en base de datos
        if opciones.is_valid() and imagenes_pregunta.is_valid():
            from django.db import transaction
            with transaction.atomic():
                self.object = form.save()
                opciones.instance = self.object
                opciones.save()
                imagenes_pregunta.instance = self.object
                imagenes_pregunta.save()
            messages.success(self.request, "Pregunta actualizada correctamente.")
        else:
            # Si hay errores de validación, volvemos a mostrar el formulario con los errores
            return self.render_to_response(self.get_context_data(form=form))

        return redirect('evaluaciones:pregunta_list')

    def get_success_url(self):
        return reverse_lazy('evaluaciones:pregunta_list')


from django.views.generic import ListView, DetailView
from curriculo.models import Materia, Tema

class PreguntaListView(ListView):
    model = Pregunta
    template_name = 'evaluaciones/pregunta_list.html'
    context_object_name = 'preguntas'
    paginate_by = 20
    
    def get_queryset(self):
        from django.db.models import Count, Q
        
        qs = super().get_queryset().select_related('tema', 'tema__materia', 'creador').prefetch_related('opciones')
        
        # Anotamos el conteo de opciones correctas
        qs = qs.annotate(
            correctas_count=Count('opciones', filter=Q(opciones__es_correcta=True))
        )
        
        q = self.request.GET.get('q', '')
        materia_id = self.request.GET.get('materia')
        tema_id = self.request.GET.get('tema')
        marcacion = self.request.GET.get('marcacion', '')
        
        if q:
            qs = qs.filter(enunciado__icontains=q)
        if materia_id:
            qs = qs.filter(tema__materia_id=materia_id)
        if tema_id:
            qs = qs.filter(tema_id=tema_id)
            
        if marcacion == 'correcta':
            qs = qs.filter(correctas_count=1)
        elif marcacion == 'error':
            qs = qs.exclude(correctas_count=1)
        elif marcacion == 'cero':
            qs = qs.filter(correctas_count=0)
        elif marcacion == 'multiples':
            qs = qs.filter(correctas_count__gt=1)
            
        return qs.order_by('-fecha_creacion')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materias'] = Materia.objects.all().order_by('nombre')
        context['temas'] = Tema.objects.select_related('materia').all().order_by('materia__nombre', 'nombre')
        context['q_val'] = self.request.GET.get('q', '')
        context['materia_val'] = self.request.GET.get('materia', '')
        context['tema_val'] = self.request.GET.get('tema', '')
        context['marcacion_val'] = self.request.GET.get('marcacion', '')
        return context

class PreguntaDetailView(LoginRequiredMixin, DetailView):
    model = Pregunta
    template_name = 'evaluaciones/pregunta_detail.html'
    context_object_name = 'pregunta'

    def get_queryset(self):
        return super().get_queryset().select_related('tema', 'tema__materia', 'bloque_contexto').prefetch_related('opciones', 'imagenes')

# ─── BloqueContexto CRUD ──────────────────────────────────────────────────────

from ..models.banco import BloqueContexto
from ..forms import BloqueContextoForm, ImagenContextoFormSet
from django.views.generic import ListView as BloqueListViewBase, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin

class BloqueContextoListView(LoginRequiredMixin, BloqueListViewBase):
    model = BloqueContexto
    template_name = 'evaluaciones/bloque_contexto_list.html'
    context_object_name = 'bloques'
    paginate_by = 20

    def get_queryset(self):
        qs = BloqueContexto.objects.prefetch_related('imagenes').select_related('materia').annotate(
            num_preguntas=models.Count('preguntas')
        ).order_by('-fecha_creacion')
        
        q = self.request.GET.get('q', '')
        materia_id = self.request.GET.get('materia', '')
        
        if q:
            qs = qs.filter(texto__icontains=q)
        if materia_id:
            qs = qs.filter(materia_id=materia_id)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from curriculo.models import Materia
        context['materias'] = Materia.objects.all().order_by('nombre')
        context['q_val'] = self.request.GET.get('q', '')
        context['materia_val'] = self.request.GET.get('materia', '')
        return context


class BloqueContextoCreateView(LoginRequiredMixin, CreateView):
    model = BloqueContexto
    form_class = BloqueContextoForm
    template_name = 'evaluaciones/bloque_contexto_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['imagenes'] = ImagenContextoFormSet(self.request.POST, self.request.FILES)
        else:
            data['imagenes'] = ImagenContextoFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        imagenes = context['imagenes']
        self.object = form.save()
        if imagenes.is_valid():
            imagenes.instance = self.object
            imagenes.save()
        messages.success(self.request, 'Bloque de contexto creado correctamente.')
        return redirect('evaluaciones:bloque_contexto_list')

    def get_success_url(self):
        return reverse_lazy('evaluaciones:bloque_contexto_list')


class BloqueContextoUpdateView(LoginRequiredMixin, UpdateView):
    model = BloqueContexto
    form_class = BloqueContextoForm
    template_name = 'evaluaciones/bloque_contexto_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['imagenes'] = ImagenContextoFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            data['imagenes'] = ImagenContextoFormSet(instance=self.object)
        data['is_edit'] = True
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        imagenes = context['imagenes']
        self.object = form.save()
        if imagenes.is_valid():
            imagenes.instance = self.object
            imagenes.save()
        messages.success(self.request, 'Bloque de contexto actualizado correctamente.')
        return redirect('evaluaciones:bloque_contexto_list')

    def get_success_url(self):
        return reverse_lazy('evaluaciones:bloque_contexto_list')


class BloqueContextoDeleteView(LoginRequiredMixin, DeleteView):
    model = BloqueContexto
    template_name = 'evaluaciones/bloque_contexto_confirm_delete.html'
    success_url = reverse_lazy('evaluaciones:bloque_contexto_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Bloque de contexto eliminado.')
        return super().delete(request, *args, **kwargs)
