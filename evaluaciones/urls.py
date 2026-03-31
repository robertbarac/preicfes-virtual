from django.urls import path
from .views.talleres import TallerCreateView, TallerUpdateView, TallerDetailView, TallerPreguntaManageView, TallerResolverView, TallerIntentoDetailView, TallerSolucionView, TallerLecturaView, TallerListView
from .views.simulacros import SimulacroCreateView, SimulacroUpdateView, SimulacroDetailView, SimulacroListView
from .views.banco import PreguntaCreateView, PreguntaListView, PreguntaUpdateView
from .views.calificaciones import MisCalificacionesView, ReporteEstudiantePDFView, ReporteRendimientoView

app_name = 'evaluaciones'

urlpatterns = [
    # Banco
    path('banco/preguntas/', PreguntaListView.as_view(), name='pregunta_list'),
    path('banco/preguntas/crear/', PreguntaCreateView.as_view(), name='pregunta_create'),
    path('banco/preguntas/<int:pk>/editar/', PreguntaUpdateView.as_view(), name='pregunta_update'),

    # Talleres
    path('talleres/', TallerListView.as_view(), name='taller_list'),
    path('talleres/crear/', TallerCreateView.as_view(), name='taller_create'),
    path('talleres/<int:pk>/', TallerDetailView.as_view(), name='taller_detail'),
    path('talleres/<int:pk>/editar/', TallerUpdateView.as_view(), name='taller_update'),
    path('talleres/<int:pk>/preguntas/', TallerPreguntaManageView.as_view(), name='taller_preguntas_manage'),
    path('talleres/<int:pk>/resolver/', TallerResolverView.as_view(), name='taller_resolver'),
    path('talleres/intentos/<int:pk>/', TallerIntentoDetailView.as_view(), name='taller_intento_detail'),
    path('talleres/<int:pk>/solucionario/', TallerSolucionView.as_view(), name='taller_solucion'),
    path('talleres/<int:pk>/lectura/', TallerLecturaView.as_view(), name='taller_lectura'),
    
    # Simulacros
    path('simulacros/', SimulacroListView.as_view(), name='simulacro_list'),
    path('simulacros/crear/', SimulacroCreateView.as_view(), name='simulacro_create'),
    path('simulacros/<int:pk>/', SimulacroDetailView.as_view(), name='simulacro_detail'),
    path('simulacros/<int:pk>/editar/', SimulacroUpdateView.as_view(), name='simulacro_update'),
    
    # Calificaciones / Reportes
    path('mis-calificaciones/', MisCalificacionesView.as_view(), name='mis_calificaciones'),
    path('reporte-pdf/<int:pk>/', ReporteEstudiantePDFView.as_view(), name='reporte_estudiante_pdf'),
    path('reporte-rendimiento/', ReporteRendimientoView.as_view(), name='reporte_rendimiento'),
]


