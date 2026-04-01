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

        # Calculate subscription dates based on active config or fallback
        from suscripciones.models import SubscriptionConfig
        config = SubscriptionConfig.objects.filter(active=True).first()
        
        if config:
            start_date = config.default_start_date
            end_date = config.default_end_date
        else:
            # Fallback if no active config exists
            start_date = timezone.now().date()
            end_date = start_date + relativedelta(years=1)
        
        Subscription.objects.create(
            user=user,
            creador=None,  # Was registered by themselves
            start_date=start_date,
            end_date=end_date
        )

        Messages.success(self.request, f"¡Tu cuenta como {user.get_role_display()} ha sido creada! Ya puedes iniciar sesión.")
        return super().form_valid(form)

from django.conf import settings
from twilio.rest import Client
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from .models import WhatsAppResetCode
from .forms import WhatsAppResetRequestForm, WhatsAppResetVerifyForm, WhatsAppResetPasswordForm
import os

class WhatsAppResetRequestView(FormView):
    template_name = 'registration/whatsapp_reset_request.html'
    form_class = WhatsAppResetRequestForm
    success_url = reverse_lazy('usuarios:whatsapp_reset_verify')

    def form_valid(self, form):
        telefono = form.cleaned_data['telefono']
        users = User.objects.filter(telefono=telefono)
        count = users.count()

        if count == 0:
            messages.error(self.request, "El número no está registrado en el sistema.")
            return self.form_invalid(form)
        elif count > 1:
            messages.error(self.request, "Hay varios usuarios con este número. Por favor, contacta a soporte.")
            return self.form_invalid(form)
        
        user = users.first()
        code = get_random_string(length=6, allowed_chars='0123456789')
        
        # Eliminar códigos antiguos no usados de este usuario (opcional para limpieza)
        WhatsAppResetCode.objects.filter(user=user, is_used=False).delete()
        WhatsAppResetCode.objects.create(user=user, code=code)

        try:
            # Twilio envio
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            twilio_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
            
            if account_sid and auth_token and twilio_number:
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    from_=f'whatsapp:{twilio_number}',
                    body=f'Tu código de seguridad para PreICFES Virtual Victor Valdez es: {code}. Este código expirará en 5 minutos.',
                    to=f'whatsapp:+57{telefono}'
                )
                messages.success(self.request, f"Te hemos enviado un código de 6 dígitos a tu WhatsApp terminado en {telefono[-4:]}.")
            else:
                 messages.warning(self.request, "Variables de entorno de Twilio no configuradas. " + f"Código en modo local: {code}")
        except Exception as e:
            messages.error(self.request, f"Error al enviar el WhatsApp: {str(e)}")
            return self.form_invalid(form)

        # Guardar teléfono en sesión para el siguiente paso
        self.request.session['reset_phone'] = telefono
        return super().form_valid(form)


class WhatsAppResetVerifyView(FormView):
    template_name = 'registration/whatsapp_reset_verify.html'
    form_class = WhatsAppResetVerifyForm
    success_url = reverse_lazy('usuarios:whatsapp_reset_password')

    def dispatch(self, request, *args, **kwargs):
        if 'reset_phone' not in request.session:
            messages.error(request, "Por favor, inicia la solicitud de recuperación primero.")
            return redirect('usuarios:whatsapp_reset_request')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['telefono'] = self.request.session.get('reset_phone')
        return context

    def form_valid(self, form):
        code_input = form.cleaned_data['code']
        telefono = self.request.session.get('reset_phone')
        user = User.objects.filter(telefono=telefono).first()

        if not user:
            messages.error(self.request, "Error interno. Usuario no encontrado.")
            return self.form_invalid(form)

        reset_code = WhatsAppResetCode.objects.filter(user=user, code=code_input).first()

        if reset_code and reset_code.is_valid():
            reset_code.is_used = True
            reset_code.save()
            self.request.session['reset_verified'] = True
            messages.success(self.request, "Código verificado correctamente.")
            return super().form_valid(form)
        else:
            messages.error(self.request, "El código es incorrecto o ha expirado.")
            return self.form_invalid(form)


class WhatsAppResetPasswordView(FormView):
    template_name = 'registration/whatsapp_reset_password.html'
    form_class = WhatsAppResetPasswordForm
    success_url = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('reset_verified') or not request.session.get('reset_phone'):
            messages.error(request, "Debes verificar tu código primero.")
            return redirect('usuarios:whatsapp_reset_request')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        telefono = self.request.session.get('reset_phone')
        user = User.objects.filter(telefono=telefono).first()

        if user:
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(self.request, "¡Tu contraseña se ha restablecido exitosamente! Ya puedes iniciar sesión.")
            # Limpiar sesión
            del self.request.session['reset_phone']
            del self.request.session['reset_verified']
            return super().form_valid(form)
        else:
            messages.error(self.request, "Usuario no válido.")
            return self.form_invalid(form)
