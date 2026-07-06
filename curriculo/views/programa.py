from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Prefetch
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django import forms

from curriculo.models import Programa, Ciclo, Modulo
from curriculo.models.core import ClaseVirtual, Asistencia
from curriculo.views.mixins import HistorialMixin, ProgramaVisibilidadMixin


# ── Forms ─────────────────────────────────────────────────────────────────────

class CicloForm(forms.ModelForm):
    class Meta:
        model = Ciclo
        fields = ['nombre', 'orden', 'visible']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'visible': forms.CheckboxInput(attrs={'class': 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
        }


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ['nombre', 'descripcion', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }


# ── Hub & Dashboard ───────────────────────────────────────────────────────────

class ProgramaHubView(LoginRequiredMixin, ListView):
    """
    Página de inicio/hub del área académica.
    Redirige automáticamente si el usuario solo tiene 1 programa activo.
    """
    model = Programa
    template_name = 'curriculo/programa_hub.html'
    context_object_name = 'programas_inscritos'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Programa.objects.filter(activo=True)
        if user.role == 'teacher':
            return user.programas_docente.filter(activo=True)
            
        # Para estudiantes, verificar suscripción activa
        from suscripciones.models import Subscription
        from django.utils import timezone
        hoy = timezone.now().date()
        suscripcion_activa = user.subscriptions.filter(active=True, end_date__gte=hoy).exists()
        if suscripcion_activa and user.programa_id and user.programa.activo:
            return Programa.objects.filter(id=user.programa_id)
        return Programa.objects.none()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        qs = self.get_queryset()
        if qs.count() == 1:
            return redirect('curriculo:programa_dashboard', slug=qs.first().slug)
        elif qs.count() == 0 and not request.user.is_superuser:
            messages.info(request, "Aún no tienes programas inscritos activos.")
            return redirect('suscripciones:mi_suscripcion')
            
        return super().dispatch(request, *args, **kwargs)


class ProgramaDashboardView(LoginRequiredMixin, ProgramaVisibilidadMixin, DetailView):
    """
    Muestra los ciclos, módulos y recursos específicos de un Programa.
    """
    model = Programa
    template_name = 'curriculo/programa_dashboard.html'
    context_object_name = 'programa'
    slug_url_kwarg = 'slug'

    def _resolver_programa(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programa = self.object
        user = self.request.user

        # Calcular si el usuario actual es profesor o administrador de este programa específico
        es_teacher = user.is_superuser or (
            user.role == 'teacher' and user.programas_docente.filter(id=programa.id).exists()
        )
        context['es_teacher'] = es_teacher

        # Filtrar los ciclos visibles para estudiantes
        if es_teacher or user.is_staff or user.is_superuser:
            ciclos_qs = programa.ciclos.all().order_by('orden')
        else:
            ciclos_qs = programa.ciclos.filter(visible=True).order_by('orden')

        # Prefetching de recursos
        from evaluaciones.models.talleres import Taller
        if es_teacher or user.is_staff or user.is_superuser:
            talleres_qs = Taller.objects.all().order_by('orden')
        else:
            talleres_qs = Taller.objects.filter(estado='publicado').order_by('orden')

        clases_qs = ClaseVirtual.objects.all()

        modulos_qs = Modulo.objects.all().prefetch_related(
            'posts',
            Prefetch('talleres', queryset=talleres_qs),
            'simulacros',
            Prefetch('clases_virtuales', queryset=clases_qs)
        ).order_by('orden')

        context['ciclos'] = ciclos_qs.prefetch_related(
            Prefetch('modulos', queryset=modulos_qs)
        )

        # Asistencias
        if user.is_authenticated and not user.is_staff:
            mis_asistencias = Asistencia.objects.filter(
                alumno=user,
                clase__modulo__ciclo__programa=programa
            ).values('clase_id', 'asistio')
            context['clases_registradas'] = {a['clase_id'] for a in mis_asistencias}
            context['clases_asistidas'] = {a['clase_id'] for a in mis_asistencias if a['asistio']}
        else:
            context['clases_registradas'] = set()
            context['clases_asistidas'] = set()

        return context


# ── Ciclo CRUD ────────────────────────────────────────────────────────────────

class CicloCreateView(LoginRequiredMixin, HistorialMixin, CreateView):
    model = Ciclo
    form_class = CicloForm
    template_name = 'curriculo/ciclo_form.html'

    def form_valid(self, form):
        programa = get_object_or_404(Programa, slug=self.kwargs.get('slug'))
        form.instance.programa = programa
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.kwargs.get('slug')})


class CicloUpdateView(LoginRequiredMixin, HistorialMixin, UpdateView):
    model = Ciclo
    form_class = CicloForm
    template_name = 'curriculo/ciclo_form.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.programa.slug})


class CicloDeleteView(LoginRequiredMixin, HistorialMixin, DeleteView):
    model = Ciclo
    template_name = 'curriculo/ciclo_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.programa.slug})


# ── Módulo CRUD ───────────────────────────────────────────────────────────────

class ModuloCreateView(LoginRequiredMixin, HistorialMixin, CreateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'

    def form_valid(self, form):
        ciclo = get_object_or_404(Ciclo, id=self.kwargs.get('ciclo_id'))
        form.instance.ciclo = ciclo
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.ciclo.programa.slug})


class ModuloUpdateView(LoginRequiredMixin, HistorialMixin, UpdateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.ciclo.programa.slug})


class ModuloDeleteView(LoginRequiredMixin, HistorialMixin, DeleteView):
    model = Modulo
    template_name = 'curriculo/modulo_confirm_delete.html'

    def get_success_url(self):
        slug = self.object.ciclo.programa.slug
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': slug})


# ── Asistencia ────────────────────────────────────────────────────────────────

class RegistrarAsistenciaView(LoginRequiredMixin, View):
    def post(self, request, clase_id):
        clase = get_object_or_404(ClaseVirtual, id=clase_id)
        programa = clase.modulo.ciclo.programa
        
        if not clase.is_active_for_attendance():
            messages.error(request, f"No puedes registrar asistencia para '{clase.titulo}' en este momento. La clase no está en curso.")
            return redirect('curriculo:programa_dashboard', slug=programa.slug)
        
        asistencia, created = Asistencia.objects.get_or_create(
            clase=clase,
            alumno=request.user,
            defaults={'asistio': True}
        )
        
        if not created:
            if asistencia.asistio:
                messages.info(request, "Ya habías registrado tu asistencia previamente.")
            else:
                asistencia.asistio = True
                asistencia.save()
                messages.success(request, f"¡Asistencia registrada exitosamente para {clase.titulo}!")
        else:
            messages.success(request, f"¡Asistencia registrada exitosamente para {clase.titulo}!")
            
        return redirect('curriculo:programa_dashboard', slug=programa.slug)
