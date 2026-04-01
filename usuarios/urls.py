from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('admin/reset-password/', views.AdminPasswordResetView.as_view(), name='admin_reset_password'),
    path('admin/registrar-usuario/', views.RegistroUsuarioView.as_view(), name='registro_interno'),
    path('admin/ventanas-registro/', views.VentanaRegistroListView.as_view(), name='ventanas_list'),
    path('admin/ventanas-registro/crear/', views.VentanaRegistroCreateView.as_view(), name='ventanas_crear'),
    path('registro/', views.RegistroPublicoView.as_view(), name='registro_publico'),
    path('reset/whatsapp/request/', views.WhatsAppResetRequestView.as_view(), name='whatsapp_reset_request'),
    path('reset/whatsapp/verify/', views.WhatsAppResetVerifyView.as_view(), name='whatsapp_reset_verify'),
    path('reset/whatsapp/new-password/', views.WhatsAppResetPasswordView.as_view(), name='whatsapp_reset_password'),
]
