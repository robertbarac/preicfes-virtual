from django import forms
from django.contrib.auth import get_user_model
from suscripciones.models import Subscription

User = get_user_model()

TIPO_REGISTRO_CHOICES = [
    ('', '--- Selecciona tipo de usuario ---'),
    ('student', 'Estudiante Presencial'),
    ('virtual_student', 'Estudiante Virtual'),
    ('teacher', 'Docente / Profesor'),
    ('staff', 'Personal Administrativo'),
]

class RegistroInternoForm(forms.ModelForm):
    # Campo propio (no del modelo) para determinar qué grupo asignar
    tipo_registro = forms.ChoiceField(
        choices=TIPO_REGISTRO_CHOICES,
        label='Tipo de Usuario',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Campos adicionales para la suscripción
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = User
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'telefono', 'username', 'programa']

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_registro')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if tipo in ['student', 'virtual_student']:
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
    tipo_registro = forms.ChoiceField(
        choices=[
            ('', '--- Selecciona tu Modalidad ---'),
            ('student', 'Estudiante Presencial (Asiste a clases físicas)'),
            ('virtual_student', 'Estudiante 100% Virtual (Plataforma)'),
        ],
        label='Modalidad',
        widget=forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'})
    )
    
    class Meta:
        model = User
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'telefono', 'username']
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'numero_documento': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'email': forms.EmailInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'telefono': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'username': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')

        return cleaned_data

class WhatsAppResetRequestForm(forms.Form):
    telefono = forms.CharField(
        max_length=10, 
        widget=forms.TextInput(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none',
            'placeholder': 'Ej. 3001234567'
        }),
        help_text="Ingresa el número de 10 dígitos sin espacios ni guiones."
    )

class WhatsAppResetVerifyForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none uppercase text-center tracking-widest',
            'placeholder': '123456'
        }),
        help_text="Ingresa el código de 6 dígitos que recibiste por WhatsApp."
    )

class WhatsAppResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'})
    )
    confirm_password = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'})
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')

        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Las contraseñas no coinciden.')
        return cleaned_data
