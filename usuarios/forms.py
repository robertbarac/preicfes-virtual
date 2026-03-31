from django import forms
from django.contrib.auth import get_user_model
from suscripciones.models import Subscription

User = get_user_model()

class RegistroInternoForm(forms.ModelForm):
    # Campos adicionales para la suscripción
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = User
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'telefono', 'username', 'role']

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if role in ['student', 'virtual_student']:
            if not start_date:
                self.add_error('start_date', 'La fecha de inicio es requerida para estudiantes.')
            if not end_date:
                self.add_error('end_date', 'La fecha de fin es requerida para estudiantes.')
            
            if start_date and end_date and start_date >= end_date:
                self.add_error('end_date', 'La fecha de fin debe ser posterior a la fecha de inicio.')

        return cleaned_data

from .models import VentanaRegistro

class VentanaRegistroForm(forms.ModelForm):
    class Meta:
        model = VentanaRegistro
        fields = ['fecha_inicio', 'fecha_fin']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }
        
class RegistroPublicoForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}))
    
    class Meta:
        model = User
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'telefono', 'username', 'role']
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'numero_documento': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'email': forms.EmailInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'telefono': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'username': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'role': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo permitimos roles de estudiantes
        self.fields['role'].choices = [
            ('', '--- Selecciona tu Modalidad ---'),
            ('student', 'Estudiante Presencial (Asiste a clases físicas)'),
            ('virtual_student', 'Estudiante 100% Virtual (Plataforma)'),
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')

        return cleaned_data
