from django import forms
from .models import PreVenta, Incidencia

class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
            result = [r for r in result if r]
            return result
        else:
            return single_file_clean(data, initial)


class PreVentaForm(forms.ModelForm):
    class Meta:
        model = PreVenta
        fields = ['nombre_padre_madre', 'telefono', 'nombre_estudiante']
        widgets = {
            'nombre_padre_madre': forms.TextInput(attrs={
                'placeholder': 'Nombre completo del padre, madre o acudiente',
                'class': 'w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
            'telefono': forms.TextInput(attrs={
                'placeholder': 'Ej. +573001234567 o 3001234567',
                'class': 'w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
            'nombre_estudiante': forms.TextInput(attrs={
                'placeholder': 'Nombre completo del estudiante',
                'class': 'w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
        }


class IncidenciaForm(forms.ModelForm):
    imagen = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
        }),
        required=False,
        label="Imágenes de Evidencia (puedes seleccionar varias)"
    )

    class Meta:
        model = Incidencia
        fields = ['etapa', 'texto']
        widgets = {
            'etapa': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
            'texto': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Escriba aquí los detalles del contacto o incidencia del día...',
                'class': 'w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
        }
