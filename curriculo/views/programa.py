from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from curriculo.models import Modulo
from curriculo.views.mixins import HistorialMixin
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
            
        return qs.prefetch_related(
            'posts', 
            'talleres', 
            'simulacros'
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
