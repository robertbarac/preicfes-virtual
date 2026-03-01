from django import forms
from .models.talleres import Taller
from .models.simulacros import Simulacro

class TallerForm(forms.ModelForm):
    class Meta:
        model = Taller
        fields = ['modulo', 'tema', 'titulo', 'descripcion', 'orden', 'intentos_permitidos']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 3}),
            'modulo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'tema': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'intentos_permitidos': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }

class SimulacroForm(forms.ModelForm):
    class Meta:
        model = Simulacro
        fields = ['modulo', 'titulo', 'fecha_apertura', 'fecha_cierre', 'duracion_minutos', 'orden']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'modulo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'fecha_apertura': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'fecha_cierre': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'duracion_minutos': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }

from .models.banco import Pregunta, Opcion, ImagenPregunta
from django.forms import inlineformset_factory

class PreguntaForm(forms.ModelForm):
    class Meta:
        model = Pregunta
        fields = ['tema', 'enunciado']
        widgets = {
            'tema': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'enunciado': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 4}),
        }

class ImagenPreguntaForm(forms.ModelForm):
    class Meta:
        model = ImagenPregunta
        fields = ['imagen', 'descripcion']
        widgets = {
            'imagen': forms.FileInput(attrs={'class': 'w-full p-2 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'}),
            'descripcion': forms.TextInput(attrs={'class': 'w-full mt-2 p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'placeholder': 'Descripción (Ej: Figura 1)'}),
        }

# Factory para vincular Imágenes dinámicamente a la Pregunta
ImagenPreguntaFormSet = inlineformset_factory(
    Pregunta, 
    ImagenPregunta, 
    form=ImagenPreguntaForm,
    extra=0, # 0 imágenes por defecto, pueden añadirse 
    can_delete=True
)

class OpcionForm(forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ['texto', 'imagen', 'es_correcta']
        widgets = {
            'texto': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'imagen': forms.FileInput(attrs={'class': 'p-1 text-sm text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-gray-50 file:text-gray-700 hover:file:bg-gray-100'}),
            'es_correcta': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500 border-gray-300'})
        }

# Factory para vincular Opciones dinámicamente a la Pregunta
OpcionFormSet = inlineformset_factory(
    Pregunta, 
    Opcion, 
    form=OpcionForm,
    extra=4, # 4 opciones por defecto (ICFES), pero el JS permite añadir más
    can_delete=True
)
