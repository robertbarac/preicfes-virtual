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
        fields = ['tipo_documento', 'numero_documento', 'first_name', 'last_name', 'email', 'username', 'role']

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if role == 'student':
            if not start_date:
                self.add_error('start_date', 'La fecha de inicio es requerida para estudiantes.')
            if not end_date:
                self.add_error('end_date', 'La fecha de fin es requerida para estudiantes.')
            
            if start_date and end_date and start_date >= end_date:
                self.add_error('end_date', 'La fecha de fin debe ser posterior a la fecha de inicio.')

        return cleaned_data
