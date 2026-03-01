from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import re

class SubscriptionCheckMiddleware:
    """
    Middleware that checks if a Student has an active subscription.
    If they do not, they are redirected to the 'mi_suscripcion' page.
    Other roles (Staff, Teachers) bypass this check.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs that a student MUST be able to access even without an active subscription
        self.allowed_urls = [
            reverse('suscripciones:mi_suscripcion'),
            reverse('login'),
            reverse('logout'),
            reverse('password_change'),
            reverse('password_change_done'),
            '/', # Landing page
            '/admin/', # Django admin panel
        ]

    def __call__(self, request):
        # 1. Bypass if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)
            
        # 1.5. Bypass if user is staff or superuser, regardless of their text 'role'
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
            
        # 2. Bypass if user is not a student
        if request.user.role != 'student':
            return self.get_response(request)

        # 3. Bypass if the path is in the allowed list or starts with allowed prefixes
        path = request.path_info
        if path in self.allowed_urls or path.startswith('/admin/') or path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # 4. Enforce subscription check for Students on protected paths
        suscripcion = request.user.subscriptions.order_by('-id').first()
        
        # If the student DOES NOT have a subscription or it's INVALID
        if not suscripcion or not suscripcion.is_valid:
            messages.error(request, 'Para acceder a esta sección de la plataforma necesitas una suscripción activa.')
            return redirect('suscripciones:mi_suscripcion')

        return self.get_response(request)
