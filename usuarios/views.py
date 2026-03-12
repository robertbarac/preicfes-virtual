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
        elif user.role in ['student', 'virtual_student']:
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
            elif user.role == 'virtual_student':
                virtual_student_group, created = Group.objects.get_or_create(name='VirtualStudent')
                user.groups.add(virtual_student_group)
        except Exception as e:
            # Silently pass or log if group creation fails, to not break registration flow
            pass

        # Si es estudiante o estudiante virtual, crear suscripción
        if user.role in ['student', 'virtual_student']:
            Subscription.objects.create(
                user=user,
                creador=self.request.user,
                start_date=form.cleaned_data['start_date'],
                end_date=form.cleaned_data['end_date']
            )
            formato_rol = "Estudiante" if user.role == 'student' else "Estudiante Virtual"
            messages.success(self.request, f"{formato_rol} {user.username} registrado con éxito. Contraseña temporal: {temporal_password}. Suscripción activada.")
        else:
            messages.success(self.request, f"Usuario {user.role} registrado con éxito. Contraseña temporal: {temporal_password}.")

        # Renderizar la respuesta con una bandera de éxito para que copien la password
        context = self.get_context_data(form=self.form_class())
        context['registration_success'] = True
        context['new_user'] = user
        context['temp_password'] = temporal_password
        return render(self.request, self.template_name, context)

from django.views.generic import TemplateView
from django.shortcuts import redirect

class LandingView(TemplateView):
    template_name = 'landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('curriculo:programa_list')
        return super().dispatch(request, *args, **kwargs)

from django.views.generic import ListView, CreateView
from django.contrib.auth.models import Group
from django.utils import timezone
from .models import VentanaRegistro
from .forms import VentanaRegistroForm, RegistroPublicoForm
from dateutil.relativedelta import relativedelta

class VentanaRegistroListView(UserPassesTestMixin, ListView):
    model = VentanaRegistro
    template_name = 'usuarios/ventanas_list.html'
    context_object_name = 'ventanas'
    
    def test_func(self):
        return self.request.user.is_superuser

class VentanaRegistroCreateView(UserPassesTestMixin, CreateView):
    model = VentanaRegistro
    form_class = VentanaRegistroForm
    template_name = 'usuarios/ventana_form.html'
    success_url = reverse_lazy('usuarios:ventanas_list')
    
    def test_func(self):
        return self.request.user.is_superuser
        
    def form_valid(self, form):
        form.instance.creador = self.request.user
        return super().form_valid(form)

class RegistroPublicoView(FormView):
    template_name = 'usuarios/registro_publico.html'
    form_class = RegistroPublicoForm
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        # Allow superusers to preview it even if closed (optional) or restrict strictly
        active_window = VentanaRegistro.objects.filter(
            fecha_inicio__lte=timezone.now(),
            fecha_fin__gte=timezone.now()
        ).exists()
        
        if not active_window:
            return render(request, 'usuarios/registro_cerrado.html', status=403)
            
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.is_staff = False  # Strictly override just in case
        user.save()

        # Group assignment
        try:
            if user.role == 'student':
                group, _ = Group.objects.get_or_create(name='Student')
                user.groups.add(group)
            elif user.role == 'virtual_student':
                group, _ = Group.objects.get_or_create(name='VirtualStudent')
                user.groups.add(group)
        except Exception:
            pass

        # Calculate a default generic subscription (e.g. 1 year from now)
        start_date = timezone.now().date()
        end_date = start_date + relativedelta(years=1)
        
        Subscription.objects.create(
            user=user,
            creador=None,  # Was registered by themselves
            start_date=start_date,
            end_date=end_date
        )

        messages.success(self.request, f"¡Tu cuenta como {user.get_role_display()} ha sido creada! Ya puedes iniciar sesión.")
        return super().form_valid(form)
