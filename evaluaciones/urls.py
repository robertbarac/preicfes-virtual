from django.urls import path
from .views.talleres import TallerCreateView, TallerUpdateView, TallerDetailView, TallerPreguntaManageView, TallerResolverView, TallerIntentoDetailView, TallerSolucionView, TallerLecturaView, TallerListView
from .views.simulacros import (
    SimulacroCreateView, SimulacroUpdateView, SimulacroDetailView, SimulacroListView,
    VentanaSimulacroCreateView, SimulacroResolverView, SimulacroEnviarView, SimulacroResultadoView
)
from .views.banco import PreguntaCreateView, PreguntaListView, PreguntaUpdateView, PreguntaDetailView, BloqueContextoListView, BloqueContextoCreateView, BloqueContextoUpdateView, BloqueContextoDeleteView
from .views.calificaciones import MisCalificacionesView, ReporteEstudiantePDFView, ReporteRendimientoView
from .views.notas_consolidadas import MisNotasView
from .views.ingles import (
    ActividadVirtualCreateView, ActividadVirtualUpdateView, ActividadVirtualDeleteView,
    ActividadVirtualResolverView, BloqueActividadCheckView, ActividadVirtualSubmitView,
    BloqueAudioUploadView, AudioSubmissionPendingListView, AudioSubmissionCalificarView,
    ActividadVirtualGestionView, BloqueActividadUpdateView, BloqueActividadDeleteView
)

app_name = 'evaluaciones'

urlpatterns = [
    # Banco — Preguntas
    path('banco/preguntas/', PreguntaListView.as_view(), name='pregunta_list'),
    path('banco/preguntas/crear/', PreguntaCreateView.as_view(), name='pregunta_create'),
    path('banco/preguntas/<int:pk>/', PreguntaDetailView.as_view(), name='pregunta_detail'),
    path('banco/preguntas/<int:pk>/editar/', PreguntaUpdateView.as_view(), name='pregunta_update'),

    # Banco — Bloques de Contexto
    path('banco/contextos/', BloqueContextoListView.as_view(), name='bloque_contexto_list'),
    path('banco/contextos/crear/', BloqueContextoCreateView.as_view(), name='bloque_contexto_create'),
    path('banco/contextos/<int:pk>/editar/', BloqueContextoUpdateView.as_view(), name='bloque_contexto_update'),
    path('banco/contextos/<int:pk>/eliminar/', BloqueContextoDeleteView.as_view(), name='bloque_contexto_delete'),

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
    path('simulacros/<int:pk>/ventana/crear/', VentanaSimulacroCreateView.as_view(), name='ventana_simulacro_create'),
    path('simulacros/<int:pk>/resolver/', SimulacroResolverView.as_view(), name='simulacro_resolver'),
    path('simulacros/<int:pk>/enviar/', SimulacroEnviarView.as_view(), name='simulacro_enviar'),
    path('simulacros/intentos/<int:pk>/', SimulacroResultadoView.as_view(), name='simulacro_resultado'),
    # Calificaciones / Reportes
    path('mis-notas/', MisNotasView.as_view(), name='mis_notas'),
    path('mis-calificaciones/', MisCalificacionesView.as_view(), name='mis_calificaciones'),
    path('reporte-pdf/<int:pk>/', ReporteEstudiantePDFView.as_view(), name='reporte_estudiante_pdf'),
    path('reporte-rendimiento/', ReporteRendimientoView.as_view(), name='reporte_rendimiento'),

    # Actividades de Inglés (Estudiante)
    path('ingles/actividades/<int:pk>/resolver/', ActividadVirtualResolverView.as_view(), name='ejercicio_ingles_resolver'),
    path('ingles/bloques/<int:pk>/check/', BloqueActividadCheckView.as_view(), name='ejercicio_ingles_check'),
    path('ingles/actividades/<int:pk>/submit/', ActividadVirtualSubmitView.as_view(), name='ejercicio_ingles_submit'),
    path('ingles/bloques/<int:pk>/audio-upload/', BloqueAudioUploadView.as_view(), name='ejercicio_ingles_audio_upload'),

    # Actividades de Inglés (Profesor / Gestión)
    path('ingles/modulo/<int:modulo_id>/actividades/crear/', ActividadVirtualCreateView.as_view(), name='ejercicio_ingles_create'),
    path('ingles/actividades/<int:pk>/editar/', ActividadVirtualUpdateView.as_view(), name='ejercicio_ingles_update'),
    path('ingles/actividades/<int:pk>/eliminar/', ActividadVirtualDeleteView.as_view(), name='ejercicio_ingles_delete'),
    
    # Gestión de bloques de ejercicios
    path('ingles/actividades/<int:pk>/bloques/', ActividadVirtualGestionView.as_view(), name='actividad_gestion_bloques'),
    path('ingles/bloques/<int:pk>/editar/', BloqueActividadUpdateView.as_view(), name='bloque_editar'),
    path('ingles/bloques/<int:pk>/eliminar/', BloqueActividadDeleteView.as_view(), name='bloque_eliminar'),

    # Revisión de entregas de audio
    path('ingles/revision/audios/', AudioSubmissionPendingListView.as_view(), name='audio_submission_pending_list'),
    path('ingles/revision/audios/<int:pk>/calificar/', AudioSubmissionCalificarView.as_view(), name='audio_submission_calificar'),
]


