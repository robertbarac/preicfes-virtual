from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from .models import Subscription

class SuscripcionListView(UserPassesTestMixin, ListView):
    model = Subscription
    template_name = 'suscripciones/suscripcion_list.html'
    context_object_name = 'suscripciones'

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_queryset(self):
        # We generally want to see students. All subscriptions belong to users (usually students).
        return Subscription.objects.select_related('user', 'creador').order_by('-id')

    def post(self, request, *args, **kwargs):
        # Handle bulk actions
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_subscriptions')

        if not selected_ids:
            messages.warning(request, "No se seleccionó ninguna suscripción.")
            return redirect('suscripciones:lista')

        subs = Subscription.objects.filter(id__in=selected_ids)
        
        if action == 'activate':
            subs.update(active=True)
            messages.success(request, f"Se han activado {subs.count()} suscripciones.")
        elif action == 'deactivate':
            subs.update(active=False)
            messages.success(request, f"Se han desactivado {subs.count()} suscripciones.")

        return redirect('suscripciones:lista')

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class MiSuscripcionDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'suscripciones/mi_suscripcion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = Subscription.objects.filter(user=self.request.user).first()
        context['suscripcion'] = subscription
        return context
