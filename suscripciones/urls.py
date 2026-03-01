from django.urls import path
from .views import SuscripcionListView, MiSuscripcionDetailView

app_name = 'suscripciones'

urlpatterns = [
    path('lista/', SuscripcionListView.as_view(), name='lista'),
    path('mi-suscripcion/', MiSuscripcionDetailView.as_view(), name='mi_suscripcion'),
]