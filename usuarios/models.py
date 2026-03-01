from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    # Admin role is handled by is_superuser and is_staff boolean properties inherited from AbstractUser
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    creador = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_registrados', help_text="Usuario que registró a esta persona (ej. Admin/Secretaría)")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
