from django.urls import path
from .views.programa import ProgramaListView, ModuloCreateView, ModuloUpdateView, RegistrarAsistenciaView

app_name = 'curriculo'

urlpatterns = [
    path('', ProgramaListView.as_view(), name='programa_list'),
    path('modulo/crear/', ModuloCreateView.as_view(), name='modulo_create'),
    path('modulo/<int:pk>/editar/', ModuloUpdateView.as_view(), name='modulo_update'),
    path('clase/<int:clase_id>/asistencia/', RegistrarAsistenciaView.as_view(), name='registrar_asistencia'),
]
