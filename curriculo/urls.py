from django.urls import path
from .views.programa import (
    ProgramaHubView, ProgramaDashboardView,
    CicloCreateView, CicloUpdateView, CicloDeleteView,
    ModuloCreateView, ModuloUpdateView, ModuloDeleteView,
    RegistrarAsistenciaView
)

app_name = 'curriculo'

urlpatterns = [
    # Hub / Redirección central
    path('', ProgramaHubView.as_view(), name='programa_list'),

    # Dashboard por programa
    path('p/<slug:slug>/', ProgramaDashboardView.as_view(), name='programa_dashboard'),

    # Ciclo CRUD
    path('p/<slug:slug>/ciclos/crear/', CicloCreateView.as_view(), name='ciclo_create'),
    path('ciclo/<int:pk>/editar/', CicloUpdateView.as_view(), name='ciclo_update'),
    path('ciclo/<int:pk>/eliminar/', CicloDeleteView.as_view(), name='ciclo_delete'),

    # Modulo CRUD
    path('ciclos/<int:ciclo_id>/modulos/crear/', ModuloCreateView.as_view(), name='modulo_create'),
    path('modulo/<int:pk>/editar/', ModuloUpdateView.as_view(), name='modulo_update'),
    path('modulo/<int:pk>/eliminar/', ModuloDeleteView.as_view(), name='modulo_delete'),

    # Asistencia
    path('clase/<int:clase_id>/asistencia/', RegistrarAsistenciaView.as_view(), name='registrar_asistencia'),
]
