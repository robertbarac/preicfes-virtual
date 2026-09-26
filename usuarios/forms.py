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
        
_STYLE_INPUT_REGISTRO = 'w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-[#155EEF] transition shadow-sm'

class RegistroPublicoForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': '••••••••'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': '••••••••'}))
    tipo_registro = forms.ChoiceField(
        choices=[
            ('', '--- Selecciona tu Modalidad ---'),
            ('student', 'Estudiante Presencial (Asiste a clases físicas)'),
            ('virtual_student', 'Estudiante 100% Virtual (Plataforma)'),
        ],
        label='Modalidad',
        widget=forms.Select(attrs={'class': _STYLE_INPUT_REGISTRO})
    )
    
    class Meta:
        model = User
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'telefono', 'username']
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': _STYLE_INPUT_REGISTRO}),
            'numero_documento': forms.TextInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'Ej: 1045236890'}),
            'first_name': forms.TextInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'Ej: Juan Andrés'}),
            'last_name': forms.TextInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'Ej: Pérez Gómez'}),
            'email': forms.EmailInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'ejemplo@correo.com'}),
            'telefono': forms.TextInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'Ej: 3001234567'}),
            'username': forms.TextInput(attrs={'class': _STYLE_INPUT_REGISTRO, 'placeholder': 'Ej: juanperez11'}),
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


class CertificadoTrabajoForm(forms.Form):
    fecha_inicio = forms.DateField(
        label="Fecha de inicio",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-2 border border-slate-700 bg-slate-900 rounded text-slate-200 focus:border-teal-500 outline-none'}),
        required=True,
        help_text="Fecha en que el profesor comenzó a trabajar en la institución."
    )
    fecha_fin = forms.DateField(
        label="Fecha de finalización",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-2 border border-slate-700 bg-slate-900 rounded text-slate-200 focus:border-teal-500 outline-none'}),
        required=True,
        help_text="Fecha en que el profesor finalizó o finalizará su periodo de trabajo."
    )

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise forms.ValidationError("La fecha de inicio debe ser anterior a la fecha de finalización.")
        return cleaned_data


class FotoPerfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['foto_perfil']
        widgets = {
            'foto_perfil': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-slate-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-bold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer transition',
                'accept': 'image/*'
            })
        }


