from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('preventas/', views.PreVentaListView.as_view(), name='preventa_list'),
    path('preventas/agregar/', views.PreVentaCreateView.as_view(), name='preventa_agregar'),
    path('preventas/<int:pk>/', views.PreVentaDetailView.as_view(), name='preventa_detail'),
    path('preventas/<int:pk>/editar/', views.PreVentaUpdateView.as_view(), name='preventa_editar'),
    path('preventas/<int:pk>/eliminar/', views.PreVentaDeleteView.as_view(), name='preventa_eliminar'),
    
    # Incidencias
    path('preventas/<int:preventa_pk>/incidencia/agregar/', views.IncidenciaCreateView.as_view(), name='incidencia_agregar'),
    path('incidencias/<int:pk>/editar/', views.IncidenciaUpdateView.as_view(), name='incidencia_editar'),
    path('incidencias/<int:pk>/eliminar/', views.IncidenciaDeleteView.as_view(), name='incidencia_eliminar'),
]
