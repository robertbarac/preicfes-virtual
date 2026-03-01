from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('admin/reset-password/', views.AdminPasswordResetView.as_view(), name='admin_reset_password'),
    path('admin/registrar-usuario/', views.RegistroUsuarioView.as_view(), name='registro_interno'),
]
