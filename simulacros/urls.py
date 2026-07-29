from django.urls import path
from . import views

app_name = 'simulacros'

urlpatterns = [
    path('grupo/<int:grupo_id>/calificar/', views.GrupoCalificarSimulacroView.as_view(), name='grupo_calificar_simulacro'),
    path('grupo/<int:grupo_id>/calificar-diagnostico/', views.GrupoCalificarDiagnosticoView.as_view(), name='grupo_calificar_diagnostico'),
    path('revisar/', views.RevisarSimulacroView.as_view(), name='revisar_simulacro'),
    path('revisar-diagnostico/', views.RevisarDiagnosticoView.as_view(), name='revisar_diagnostico'),
    path('resultados/', views.ResultadosSimulacroListView.as_view(), name='resultados_simulacros'),
    path('resultados-diagnosticos/', views.ResultadosDiagnosticoListView.as_view(), name='resultados_diagnosticos'),
    path('resultados/pdf/', views.DescargarResultadosPDFView.as_view(), name='descargar_resultados_pdf'),
    path('resultados/pdf-reales/', views.DescargarResultadosRealesPDFView.as_view(), name='descargar_resultados_reales_pdf'),
    path('resultados/informe-directivo/', views.DescargarInformeDirectivoPDFView.as_view(), name='descargar_informe_directivo'),
    path('resultados/<int:resultado_pk>/pdf/', views.DescargarResultadoIndividualPDFView.as_view(), name='descargar_resultado_individual_pdf'),
]
