from django.db import models
from django.conf import settings
from django.utils import timezone

class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='suscripciones_creadas')
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)

    @property
    def is_valid(self):
        return self.active and self.end_date >= timezone.now().date()

    def __str__(self):
        status = "Valid" if self.is_valid else "Expired/Inactive"
        return f"Subscription for {self.user.username} ({status})"

class SubscriptionConfig(models.Model):
    default_start_date = models.DateField(help_text="Fecha de inicio por defecto para nuevas suscripciones automáticas")
    default_end_date = models.DateField(help_text="Fecha de fin por defecto para nuevas suscripciones automáticas")
    active = models.BooleanField(default=True, help_text="Marcar para usar esta configuración (solo una debería estar activa)")

    class Meta:
        verbose_name = "Configuración de Suscripción"
        verbose_name_plural = "Configuraciones de Suscripciones"

    def __str__(self):
        return f"Config ({self.default_start_date} a {self.default_end_date}) - {'Activa' if self.active else 'Inactiva'}"
