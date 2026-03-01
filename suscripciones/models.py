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
