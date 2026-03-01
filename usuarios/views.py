from django.views.generic import FormView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import render
from django import forms
from django.contrib.auth import get_user_model
import secrets
import string

User = get_user_model()

class AdminPasswordResetForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        label="Seleccionar Usuario",
        widget=forms.Select(attrs={'class': 'form-select block w-full'})
    )

class AdminPasswordResetView(UserPassesTestMixin, FormView):
    template_name = 'usuarios/admin_password_reset.html'
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy('usuarios:admin_reset_password')
    
    def test_func(self):
        return self.request.user.is_superuser
        
    def form_valid(self, form):
        user = form.cleaned_data['user']
        
        # Generar contraseña aleatoria (10 caracteres, letras y números)
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(10))
        
        # Asignarla
        user.set_password(new_password)
        user.save()
        
        # Renderear el template con el resultado directamente para que el admin copie la contraseña
        context = self.get_context_data(form=form)
        context['reset_success'] = True
        context['affected_user'] = user
        context['new_password'] = new_password
        return render(self.request, self.template_name, context)

from .forms import RegistroInternoForm
from suscripciones.models import Subscription
from django.contrib import messages

class RegistroUsuarioView(UserPassesTestMixin, FormView):
    template_name = 'usuarios/registro_interno.html'
    form_class = RegistroInternoForm
    success_url = reverse_lazy('usuarios:registro_interno')

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def form_valid(self, form):
        from django.contrib.auth.models import Group
        
        user = form.save(commit=False)
        user.creador = self.request.user
        
        # Asignar nivel de Staff basado en el Rol elegido
        if user.role == 'teacher':
            user.is_staff = True
        elif user.role == 'student':
            user.is_staff = False
            
        # Generar contraseña temporal segura
        alphabet = string.ascii_letters + string.digits
        temporal_password = ''.join(secrets.choice(alphabet) for i in range(10))
        user.set_password(temporal_password)
        user.save()

        # Asignación de Grupos de Permisos
        try:
            if user.role == 'teacher':
                teacher_group, created = Group.objects.get_or_create(name='Teacher')
                user.groups.add(teacher_group)
            elif user.role == 'student':
                student_group, created = Group.objects.get_or_create(name='Student')
                user.groups.add(student_group)
        except Exception as e:
            # Silently pass or log if group creation fails, to not break registration flow
            pass

        # Si es estudiante, crear suscripción
        if user.role == 'student':
            Subscription.objects.create(
                user=user,
                creador=self.request.user,
                start_date=form.cleaned_data['start_date'],
                end_date=form.cleaned_data['end_date']
            )
            messages.success(self.request, f"Estudiante {user.username} registrado con éxito. Contraseña temporal: {temporal_password}. Suscripción activada.")
        else:
            messages.success(self.request, f"Usuario {user.role} registrado con éxito. Contraseña temporal: {temporal_password}.")

        # Renderizar la respuesta con una bandera de éxito para que copien la password
        context = self.get_context_data(form=self.form_class())
        context['registration_success'] = True
        context['new_user'] = user
        context['temp_password'] = temporal_password
        return render(self.request, self.template_name, context)
