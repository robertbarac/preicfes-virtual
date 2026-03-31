from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.db.models import Prefetch
from django.core.cache import cache
from curriculo.models import Modulo
from curriculo.views.mixins import HistorialMixin
from evaluaciones.models.talleres import Taller
from django import forms
from curriculo.cache_keys import PROGRAMA_CACHE_KEY, PROGRAMA_CACHE_TTL


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ['nombre', 'descripcion', 'orden', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'activo': forms.CheckboxInput(attrs={'class': 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
        }


def _get_modulos_para_estudiante():
    """
    Devuelve la lista de módulos activos con talleres publicados, posts,
    simulacros y clases virtuales. Se cachea 24h y se invalida por signals.
    """
    cached = cache.get(PROGRAMA_CACHE_KEY)
    if cached is not None:
        return cached

    from curriculo.models.core import ClaseVirtual

    talleres_prefetch = Prefetch(
        'talleres',
        queryset=Taller.objects.filter(estado='publicado').order_by('orden')
    )
    clases_prefetch = Prefetch(
        'clases_virtuales',
        queryset=ClaseVirtual.objects.all()
    )

    modulos = list(
        Modulo.objects.filter(activo=True)
        .prefetch_related('posts', talleres_prefetch, 'simulacros', clases_prefetch)
        .order_by('orden')
    )
    cache.set(PROGRAMA_CACHE_KEY, modulos, PROGRAMA_CACHE_TTL)
    return modulos


class ProgramaListView(ListView):
    model = Modulo
    template_name = 'curriculo/programa_list.html'
    context_object_name = 'modulos'

    def get_queryset(self):
        if self.request.user.is_staff:
            # Staff ve todo, sin caché, para poder ver borradores
            from curriculo.models.core import ClaseVirtual
            talleres_prefetch = Prefetch('talleres', queryset=Taller.objects.all())
            clases_prefetch = Prefetch('clases_virtuales', queryset=ClaseVirtual.objects.all())
            return (
                Modulo.objects.all()
                .prefetch_related('posts', talleres_prefetch, 'simulacros', clases_prefetch)
                .order_by('orden')
            )

        # Estudiantes: queryset compartido desde caché
        return _get_modulos_para_estudiante()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Inyectar asistencias personales solo para estudiantes no-staff
        # Esto NO va al caché — datos personales siempre llegan fresco de DB
        if not self.request.user.is_staff:
            from curriculo.models.core import Asistencia
            mis_asistencias = Asistencia.objects.filter(
                alumno=self.request.user
            ).values('clase_id', 'asistio')
            # Dos sets simples para usar con |in| en el template sin filtros custom
            context['clases_registradas'] = {a['clase_id'] for a in mis_asistencias}
            context['clases_asistidas'] = {a['clase_id'] for a in mis_asistencias if a['asistio']}
        else:
            context['clases_registradas'] = set()
            context['clases_asistidas'] = set()

        return context


class ModuloCreateView(HistorialMixin, CreateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'
    
    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list')

class ModuloUpdateView(HistorialMixin, UpdateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'
    
    def get_success_url(self):
        # Tras editar también redirigimos al listado
        return reverse_lazy('curriculo:programa_list')


from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from curriculo.models.core import ClaseVirtual, Asistencia
from django.contrib.auth.mixins import LoginRequiredMixin

class RegistrarAsistenciaView(LoginRequiredMixin, View):
    def post(self, request, clase_id):
        clase = get_object_or_404(ClaseVirtual, id=clase_id)
        
        # 1. Validar que la ventana de tiempo sea la correcta
        if not clase.is_active_for_attendance():
            messages.error(request, f"No puedes registrar asistencia para '{clase.titulo}' en este momento. La clase no está en curso.")
            return redirect('curriculo:programa_list')
        
        # 2. Buscar o crear el registro de asistencia del alumno
        # Normalmente debió crearse por el Signal al crear la clase, pero si el alumno se 
        # registró después, usamos get_or_create como fallback seguro
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
            
        return redirect('curriculo:programa_list')
