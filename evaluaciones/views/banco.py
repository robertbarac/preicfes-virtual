from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, UpdateView
from django.contrib import messages
from ..models.banco import Pregunta, Opcion, ImagenPregunta
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
        
        self.object = form.save()
        
        if opciones.is_valid() and imagenes_pregunta.is_valid():
            opciones.instance = self.object
            opciones.save()
            
            imagenes_pregunta.instance = self.object
            imagenes_pregunta.save()
            
            # Verificar si se indicó al menos una respuesta correcta
            tiene_correcta = False
            for form_opcion in opciones.forms:
                if form_opcion.cleaned_data and not form_opcion.cleaned_data.get('DELETE', False):
                    if form_opcion.cleaned_data.get('es_correcta', False):
                        tiene_correcta = True
                        break
            
            if not tiene_correcta:
                messages.warning(self.request, "Atención: Guardaste la pregunta sin marcar ninguna opción como correcta.")
            else:
                messages.success(self.request, "Pregunta guardada correctamente.")
        else:
            return self.render_to_response(self.get_context_data(form=form))
            
        # Refill back parameter or list
        taller_id = self.request.GET.get('taller')
        if taller_id:
            return redirect('evaluaciones:taller_preguntas_manage', pk=taller_id)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_list') # O el listado global de preguntas cuando exista
