from django import forms
from .models import Alumno, Clase, Materia, Grupo, Inasistencia
from django.utils import timezone

class AlumnoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases base a todos los campos
        for field_name, field in self.fields.items():
            # Clases base para todos los inputs
            base_classes = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            
            # Añadir clases específicas según el tipo de campo
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.NumberInput)):
                field.widget.attrs.update({'class': f'{base_classes}'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': f'{base_classes} py-2'})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({
                    'class': f'{base_classes}',
                    'type': 'date'
                })
            
            # Mejorar los placeholders
            if field_name in ['celular', 'celular_padre', 'celular_madre']:
                field.widget.attrs['placeholder'] = '3XX XXX XXXX'
            elif 'nombres' in field_name:
                field.widget.attrs['placeholder'] = 'Ingrese los nombres'
            elif 'apellido' in field_name:
                field.widget.attrs['placeholder'] = 'Ingrese el apellido'
            elif field_name == 'identificacion':
                field.widget.attrs['placeholder'] = 'Número de identificación'

    class Meta:
        model = Alumno
        fields = [
            'nombres', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'identificacion', 'tipo_identificacion',
            'celular', 
            'nombres_padre', 'primer_apellido_padre', 'segundo_apellido_padre', 'celular_padre',
            'nombres_madre', 'primer_apellido_madre', 'segundo_apellido_madre', 'celular_madre',
            'municipio', 'grupo_actual'
        ]
        
        help_texts = {
            'celular': 'Número de celular del estudiante',
            'celular_padre': 'Número de celular del padre',
            'celular_madre': 'Número de celular de la madre',
            'fecha_nacimiento': 'Fecha de nacimiento del estudiante',
            'identificacion': 'Número de documento de identidad',
            'municipio': 'Ciudad de residencia',
            'grupo_actual': 'Grupo al que pertenece el estudiante'
        }


class ClaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        salon_id = kwargs.pop('salon_id', None)
        fecha = kwargs.pop('fecha', None)
        super().__init__(*args, **kwargs)
        
        # Aplicar clases base a todos los campos
        for field_name, field in self.fields.items():
            # Clases base para todos los inputs
            base_classes = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.NumberInput)):
                field.widget.attrs.update({'class': f'{base_classes}'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': f'{base_classes} py-2'})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({
                    'class': f'{base_classes}',
                    'type': 'date'
                })
        
        # Si se proporciona un salon_id, preseleccionarlo y hacerlo de solo lectura
        if salon_id:
            self.fields['salon'].initial = salon_id
            self.fields['salon'].widget.attrs['readonly'] = True
            self.fields['salon'].widget.attrs['disabled'] = True
            # Filtrar grupos que pertenecen al salón seleccionado
            self.fields['grupo'].queryset = Grupo.objects.filter(salon_id=salon_id)
        
        # Si se proporciona una fecha, preseleccionarla
        if fecha:
            self.fields['fecha'].initial = fecha
            
    class Meta:
        model = Clase
        fields = ['fecha', 'salon', 'materia', 'profesor', 'grupo', 'horario', 'estado', 'taller']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {
            'fecha': 'Fecha de la clase',
            'salon': 'Salón donde se impartirá la clase',
            'materia': 'Materia a impartir',
            'profesor': 'Profesor que impartirá la clase',
            'grupo': 'Grupo que recibirá la clase',
            'horario': 'Horario de la clase',
            'estado': 'Estado actual de la clase',
            'taller': 'Taller interactivo opcional asignado a esta clase presencial'
        }


class InasistenciaForm(forms.ModelForm):
    class Meta:
        model = Inasistencia
        fields = ['motivo', 'justificada', 'soporte']
        widgets = {
            'motivo': forms.Textarea(attrs={'rows': 3}),
            'justificada': forms.CheckboxInput(),
        }
        help_texts = {
            'motivo': 'Describe la razón de la inasistencia.',
            'justificada': 'Marca esta casilla si el alumno presentó una excusa válida.',
            'soporte': 'Sube una imagen de la excusa (opcional).',
        }
