from django import forms
from .models.talleres import Taller
from .models.simulacros import Simulacro, VentanaSimulacro

class TallerForm(forms.ModelForm):
    class Meta:
        model = Taller
        fields = ['modulo', 'tema', 'titulo', 'descripcion', 'estado', 'orden', 'intentos_permitidos']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'modulo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'tema': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'bloque_contexto': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'intentos_permitidos': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }


class SimulacroForm(forms.ModelForm):
    class Meta:
        model = Simulacro
        fields = ['modulo', 'titulo', 'estado', 'duracion_minutos', 'orden']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'modulo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'estado': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'duracion_minutos': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }


class VentanaSimulacroForm(forms.ModelForm):
    class Meta:
        model = VentanaSimulacro
        fields = ['fecha_apertura', 'fecha_cierre']
        widgets = {
            'fecha_apertura': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}
            ),
            'fecha_cierre': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        apertura = cleaned.get('fecha_apertura')
        cierre = cleaned.get('fecha_cierre')
        if apertura and cierre and cierre <= apertura:
            raise forms.ValidationError('La fecha de cierre debe ser posterior a la fecha de apertura.')
        return cleaned


from .models.banco import Pregunta, Opcion, ImagenPregunta, BloqueContexto, ImagenContexto
from django.forms import inlineformset_factory

class PreguntaForm(forms.ModelForm):
    class Meta:
        model = Pregunta
        fields = ['tema', 'bloque_contexto', 'enunciado']
        widgets = {
            'tema': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'bloque_contexto': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'enunciado': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none tinymce-enunciado', 'rows': 4}),
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
            'texto': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none tinymce-opcion', 'rows': 3}),
            'imagen': forms.FileInput(attrs={'class': 'p-1 text-sm text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-gray-50 file:text-gray-700 hover:file:bg-gray-100'}),
            'es_correcta': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500 border-gray-300'})
        }

from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError

class BaseOpcionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        
        # Si alguno de los formularios individuales ya tiene un error de validación de campo,
        # no realizamos la validación del formset completo.
        if any(self.errors):
            return
            
        correctas_count = 0
        total_forms = 0
        
        for form in self.forms:
            # Si el formulario está marcado para borrado, lo ignoramos.
            if self.can_delete and self._should_delete_form(form):
                continue
            
            # Solo consideramos formularios que tengan datos (es decir, que no estén vacíos en el FormSet extra)
            if form.cleaned_data:
                # Verificamos si tiene texto o imagen, o si ya existe en la base de datos
                if form.cleaned_data.get('texto') or form.cleaned_data.get('imagen') or form.instance.pk:
                    total_forms += 1
                    if form.cleaned_data.get('es_correcta'):
                        correctas_count += 1
                        
        if total_forms > 0:
            if correctas_count == 0:
                raise ValidationError("Debe marcar exactamente UNA opción como correcta. Actualmente hay 0 marcadas.")
            elif correctas_count > 1:
                raise ValidationError(f"Debe marcar exactamente UNA opción como correcta. Actualmente hay {correctas_count} marcadas.")

# Factory para vincular Opciones dinámicamente a la Pregunta
OpcionFormSet = inlineformset_factory(
    Pregunta, 
    Opcion, 
    form=OpcionForm,
    formset=BaseOpcionFormSet,
    extra=4, # 4 opciones por defecto (ICFES), pero el JS permite añadir más
    can_delete=True
)


# ─── BloqueContexto ───────────────────────────────────────────────────────────

class ImagenContextoForm(forms.ModelForm):
    class Meta:
        model = ImagenContexto
        fields = ['imagen', 'descripcion']
        widgets = {
            'imagen': forms.FileInput(attrs={'class': 'w-full p-2 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'}),
            'descripcion': forms.TextInput(attrs={'class': 'w-full mt-2 p-2 border border-gray-300 rounded focus:border-blue-500 outline-none', 'placeholder': 'Descripción (Ej: Figura 1)'}),
        }

ImagenContextoFormSet = inlineformset_factory(
    BloqueContexto,
    ImagenContexto,
    form=ImagenContextoForm,
    extra=0,
    can_delete=True,
)

class BloqueContextoForm(forms.ModelForm):
    class Meta:
        model = BloqueContexto
        fields = ['materia', 'texto']
        widgets = {
            'materia': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-blue-500 outline-none'}),
            'texto': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-blue-500 outline-none tinymce-contexto', 'rows': 6}),
        }
