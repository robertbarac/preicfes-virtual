import json
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django import forms

from curriculo.models import Modulo, Programa
from evaluaciones.models.ingles import ActividadVirtual, BloqueActividad, IntentoActividad, IntentoAudioBloque
from curriculo.views.mixins import HistorialMixin, ProgramaVisibilidadMixin


# ── Forms ─────────────────────────────────────────────────────────────────────

class BloqueActividadForm(forms.ModelForm):
    class Meta:
        model = BloqueActividad
        fields = ['tipo', 'consigna', 'contenido', 'distractores', 'orden']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'w-full p-2.5 border border-gray-300 rounded focus:ring focus:ring-indigo-150 outline-none'}),
            'consigna': forms.Textarea(attrs={'rows': 2, 'class': 'w-full p-2.5 border border-gray-300 rounded focus:ring focus:ring-indigo-150 outline-none', 'placeholder': 'Escribe las instrucciones para el alumno...'}),
            'contenido': forms.Textarea(attrs={'rows': 4, 'class': 'w-full p-2.5 border border-gray-300 rounded font-mono text-sm focus:ring focus:ring-indigo-150 outline-none', 'placeholder': 'Ejemplo:\n- Drag & Drop: "I want a [dog] and a [cat]."\n- Dropdown: "She [likes|like|liking] to learn english."\n- Escritura: "We [run] (run) every morning."\n- Audio: "Texto que el estudiante debe leer y pronunciar en voz alta."'}),
            'distractores': forms.TextInput(attrs={'class': 'w-full p-2.5 border border-gray-300 rounded focus:ring focus:ring-indigo-150 outline-none', 'placeholder': 'opcion1, opcion2 (separadas por comas, solo para Drag & Drop)'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2.5 border border-gray-300 rounded focus:ring focus:ring-indigo-150 outline-none'}),
        }


# ── Actividad CRUD ────────────────────────────────────────────────────────────

class ActividadVirtualCreateView(LoginRequiredMixin, HistorialMixin, CreateView):
    model = ActividadVirtual
    fields = ['titulo', 'descripcion', 'orden']
    template_name = 'evaluaciones/ingles/actividad_form.html'

    def form_valid(self, form):
        modulo = get_object_or_404(Modulo, id=self.kwargs.get('modulo_id'))
        form.instance.modulo = modulo
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.modulo.ciclo.programa.slug})


class ActividadVirtualUpdateView(LoginRequiredMixin, HistorialMixin, UpdateView):
    model = ActividadVirtual
    fields = ['titulo', 'descripcion', 'orden']
    template_name = 'evaluaciones/ingles/actividad_form.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.modulo.ciclo.programa.slug})


class ActividadVirtualDeleteView(LoginRequiredMixin, HistorialMixin, DeleteView):
    model = ActividadVirtual
    template_name = 'evaluaciones/ingles/actividad_confirm_delete.html'

    def get_success_url(self):
        slug = self.object.modulo.ciclo.programa.slug
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': slug})


# ── Gestión de Bloques de la Actividad (Frontend) ──────────────────────────────

class ActividadVirtualGestionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Vista única para que el docente liste y agregue bloques de ejercicios a una actividad.
    """
    def test_func(self):
        return self.request.user.role == 'teacher' or self.request.user.is_superuser

    def get(self, request, pk):
        actividad = get_object_or_404(ActividadVirtual, pk=pk)
        bloques = actividad.bloques.all().order_by('orden')
        form = BloqueActividadForm()
        return render(request, 'evaluaciones/ingles/gestion_bloques.html', {
            'actividad': actividad,
            'bloques': bloques,
            'form': form
        })

    def post(self, request, pk):
        actividad = get_object_or_404(ActividadVirtual, pk=pk)
        form = BloqueActividadForm(request.POST)
        if form.is_valid():
            bloque = form.save(commit=False)
            bloque.actividad = actividad
            bloque.save()
            messages.success(request, "Bloque agregado exitosamente a la actividad.")
            return redirect('evaluaciones:actividad_gestion_bloques', pk=pk)
        
        bloques = actividad.bloques.all().order_by('orden')
        return render(request, 'evaluaciones/ingles/gestion_bloques.html', {
            'actividad': actividad,
            'bloques': bloques,
            'form': form
        })


class BloqueActividadUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Edición de un bloque de ejercicio específico.
    """
    model = BloqueActividad
    form_class = BloqueActividadForm
    template_name = 'evaluaciones/ingles/bloque_form.html'

    def test_func(self):
        return self.request.user.role == 'teacher' or self.request.user.is_superuser

    def get_success_url(self):
        return reverse_lazy('evaluaciones:actividad_gestion_bloques', kwargs={'pk': self.object.actividad.pk})


class BloqueActividadDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Eliminación de un bloque de ejercicio específico.
    """
    def test_func(self):
        return self.request.user.role == 'teacher' or self.request.user.is_superuser

    def post(self, request, pk):
        bloque = get_object_or_404(BloqueActividad, pk=pk)
        actividad_id = bloque.actividad_id
        bloque.delete()
        messages.success(request, "Bloque de ejercicio eliminado.")
        return redirect('evaluaciones:actividad_gestion_bloques', pk=actividad_id)


# ── Resolver e Interacción de Estudiante ──────────────────────────────────────

class ActividadVirtualResolverView(LoginRequiredMixin, ProgramaVisibilidadMixin, DetailView):
    """
    Renders the unified solving interface for students containing all blocks.
    """
    model = ActividadVirtual
    template_name = 'evaluaciones/ingles/resolver.html'
    context_object_name = 'actividad'

    def _resolver_programa(self):
        self.actividad = self.get_object()
        return self.actividad.modulo.ciclo.programa

    def _resolver_ciclo(self):
        return self.actividad.modulo.ciclo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Último intento del estudiante
        ultimo_intento = IntentoActividad.objects.filter(
            actividad=self.object, usuario=self.request.user
        ).order_by('-fecha').first()
        
        # Obtener los audios subidos en el último intento (si existen)
        audios = {}
        if ultimo_intento:
            for audio in ultimo_intento.audios_intento.all():
                audios[audio.bloque_id] = audio

        # Permitir al docente gestionar si está visualizando la vista
        es_teacher = self.request.user.is_superuser or (
            self.request.user.role == 'teacher' and self.request.user.programas_docente.filter(id=self.object.modulo.ciclo.programa.id).exists()
        )

        context['ultimo_intento'] = ultimo_intento
        context['audios'] = audios
        context['programa'] = self.object.modulo.ciclo.programa
        context['es_teacher'] = es_teacher
        return context


# ── AJAX Check ──

class BloqueActividadCheckView(LoginRequiredMixin, View):
    """
    Realiza una retroalimentación instantánea (Check) para un bloque específico.
    """
    def post(self, request, pk):
        bloque = get_object_or_404(BloqueActividad, pk=pk)
        body = json.loads(request.body or '{}')
        student_answers = body.get('answers', {})

        text = bloque.contenido
        raw_gaps = re.findall(r'\[([^\]]+)\]', text)
        
        results = []
        for idx, gap in enumerate(raw_gaps):
            if bloque.tipo == 'fill_dropdown':
                correct = gap.split('|')[0].strip()
            else:
                correct = gap.strip()
                
            student_ans = student_answers.get(str(idx), '').strip()
            is_correct = (student_ans.lower() == correct.lower())
            
            results.append({
                'idx': idx,
                'correct': is_correct,
                'expected': correct if not is_correct else None
            })
            
        return JsonResponse({'results': results})


# ── Submission Actividad Completa ──

class ActividadVirtualSubmitView(LoginRequiredMixin, View):
    """
    Guarda el intento de la actividad completa y calcula la nota.
    """
    def post(self, request, pk):
        actividad = get_object_or_404(ActividadVirtual, pk=pk)
        body = json.loads(request.body or '{}')
        respuestas = body.get('respuestas', {})
        audio_ids = body.get('audio_ids', [])

        bloques = actividad.bloques.all()
        total_gaps = 0
        correct_gaps = 0
        retro = {}

        for b in bloques:
            if b.tipo == 'audio_task':
                continue
                
            text = b.contenido
            raw_gaps = re.findall(r'\[([^\]]+)\]', text)
            b_answers = respuestas.get(str(b.id), {})
            b_retro = {}
            
            for idx, gap in enumerate(raw_gaps):
                total_gaps += 1
                if b.tipo == 'fill_dropdown':
                    correct = gap.split('|')[0].strip()
                else:
                    correct = gap.strip()
                    
                student_ans = b_answers.get(str(idx), '').strip()
                is_correct = (student_ans.lower() == correct.lower())
                if is_correct:
                    correct_gaps += 1
                    
                b_retro[str(idx)] = {
                    'correct': is_correct,
                    'expected': correct,
                    'submitted': student_ans
                }
            retro[str(b.id)] = b_retro

        puntaje = (correct_gaps / total_gaps * 100) if total_gaps > 0 else 100
        
        intento = IntentoActividad.objects.create(
            actividad=actividad,
            usuario=request.user,
            respuestas=respuestas,
            retroalimentacion=retro,
            puntaje=puntaje
        )

        # Vincular los audios subidos en esta sesión a este intento
        if audio_ids:
            IntentoAudioBloque.objects.filter(
                id__in=audio_ids, usuario=request.user
            ).update(intento=intento)

        return JsonResponse({
            'success': True,
            'puntaje': round(puntaje, 1),
            'correctas': correct_gaps,
            'total': total_gaps,
            'retro': retro
        })


# ── Audio Upload por Bloque ──

class BloqueAudioUploadView(LoginRequiredMixin, View):
    """
    Sube un fragmento de audio asociado a un bloque específico de la actividad.
    """
    def post(self, request, pk):
        bloque = get_object_or_404(BloqueActividad, pk=pk)
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return JsonResponse({'error': 'No se recibió ningún archivo de audio'}, status=400)

        sub = IntentoAudioBloque.objects.create(
            bloque=bloque,
            usuario=request.user,
            audio=audio_file
        )

        return JsonResponse({
            'success': True,
            'audio_id': sub.id
        })


# ── Teacher Audio Review Panel ────────────────────────────────────────────────

class AudioSubmissionPendingListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = IntentoAudioBloque
    template_name = 'evaluaciones/ingles/audio_pending_list.html'
    context_object_name = 'submissions'

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return IntentoAudioBloque.objects.filter(revisado=False).order_by('-fecha')
        
        return IntentoAudioBloque.objects.filter(
            bloque__actividad__modulo__ciclo__programa__in=user.programas_docente.all(),
            revisado=False
        ).order_by('-fecha')


class AudioSubmissionCalificarView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def post(self, request, pk):
        sub = get_object_or_404(IntentoAudioBloque, pk=pk)
        calif = request.POST.get('calificacion')
        comment = request.POST.get('comentario', '').strip()

        try:
            sub.calificacion = float(calif)
            sub.comentario_profe = comment
            sub.revisado = True
            sub.save()
            messages.success(request, f"Audio de {sub.usuario.username} calificado con {calif}.")
        except (ValueError, TypeError):
            messages.error(request, "Calificación inválida.")

        return redirect('evaluaciones:audio_submission_pending_list')
