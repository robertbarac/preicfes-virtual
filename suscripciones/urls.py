from django.urls import path
from .views import SuscripcionListView

app_name = 'suscripciones'

urlpatterns = [
    path('lista/', SuscripcionListView.as_view(), name='lista'),
]