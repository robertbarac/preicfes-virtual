from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.db.models import Prefetch
from curriculo.models import Modulo
from curriculo.views.mixins import HistorialMixin
from evaluaciones.models.talleres import Taller
from django import forms

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

class ProgramaListView(ListView):
    model = Modulo
    template_name = 'curriculo/programa_list.html'
    context_object_name = 'modulos'

    def get_queryset(self):
        # Prefetch related objects to avoid N+1 queries in the template
        # Mostramos también los inactivos si es staff o podemos aplicar lógica diferente
        qs = Modulo.objects.all()
        
        if not self.request.user.is_staff:
            qs = qs.filter(activo=True)
            # Filtramos los talleres por estado='publicado' usando Prefetch para estudiantes
            talleres_prefetch = Prefetch('talleres', queryset=Taller.objects.filter(estado='publicado'))
            # Para las clases virtuales, prebuscamos las asistencias correspondientes al estudiante
            from curriculo.models.core import Asistencia
            clases_prefetch = Prefetch(
                'clases_virtuales',
                queryset=ClaseVirtual.objects.prefetch_related(
                    Prefetch('asistencias', queryset=Asistencia.objects.filter(alumno=self.request.user), to_attr='mi_asistencia')
                )
            )
        else:
            talleres_prefetch = Prefetch('talleres')
            clases_prefetch = Prefetch('clases_virtuales')
            
        return qs.prefetch_related(
            'posts', 
            talleres_prefetch, 
            'simulacros',
            clases_prefetch
        ).order_by('orden')

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
