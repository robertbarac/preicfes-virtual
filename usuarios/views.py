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
