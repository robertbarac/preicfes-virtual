from django.urls import path
from .views import (
    generar_cuotas_view,
    BecadosListView, GraficaIngresosView, GraficaEgresosView,
    CuotasVencidasListView, DeudaCreateView, DeudaUpdateView, CuotaCreateView, CuotaUpdateView, CuotaDeleteView, ReciboPDFView,
    PazSalvoListView, PazSalvoPDFView, ProximosPagosListView, InformeDiarioView, generar_pdf_informe, MantenimientoCarteraView, toggle_edicion_deuda,
    AcuerdoPagoListView, AcuerdoPagoCreateView, AcuerdoPagoUpdateView, generar_pdf_retirados_view,
    AlumnosSinCarteraListView,
    SaldosListView,
    LimboListView
)

app_name = 'cartera'

from .views.alumnos_retirados_list import AlumnosRetiradosListView

urlpatterns = [
    # path('abonos-hechos/', AbonosHechosListView.as_view(), name='abonos_hechos'),
    # path('cartera/', CarteraListView.as_view(), name='cartera'),
    path('saldos/', SaldosListView.as_view(), name='saldos_list'),
    path('limbo/', LimboListView.as_view(), name='limbo_list'),
    path('grafica/', GraficaIngresosView.as_view(), name='grafica'),
    path('grafica-egresos/', GraficaEgresosView.as_view(), name='grafica_egresos'),
    path('mantenimiento/', MantenimientoCarteraView.as_view(), name='mantenimiento'),
    path('cuotas-vencidas/', CuotasVencidasListView.as_view(), name='cuotas_vencidas'),
    path('alumnos-sin-cartera/', AlumnosSinCarteraListView.as_view(), name='alumnos_sin_cartera'),
    path('deuda/agregar/<int:alumno_id>/', DeudaCreateView.as_view(), name='deuda_agregar'),
    path('cuota/agregar/<int:deuda_id>/', CuotaCreateView.as_view(), name='cuota_agregar'),
    path('cuota/editar/<int:pk>/', CuotaUpdateView.as_view(), name='cuota_editar'),
    path('cuota/eliminar/<int:pk>/', CuotaDeleteView.as_view(), name='cuota_eliminar'),
    path('cuota/recibo/<int:pk>/', ReciboPDFView.as_view(), name='cuota_recibo'),
    path('proximos-pagos/', ProximosPagosListView.as_view(), name='proximos_pagos'),
    path('paz-salvo/', PazSalvoListView.as_view(), name='paz_salvo'),
    path('becados/', BecadosListView.as_view(), name='becados_list'),
    path('paz-salvo/pdf/<int:alumno_id>/', PazSalvoPDFView.as_view(), name='paz_salvo_pdf'),
    path('informe-diario/', InformeDiarioView.as_view(), name='informe_diario'),
    path('informe/pdf/', generar_pdf_informe, name='generar_informe_pdf'),
    path('alumno/<int:alumno_id>/generar-cuotas/', generar_cuotas_view, name='generar_cuotas'),
    path('retirados/', AlumnosRetiradosListView.as_view(), name='alumnos_retirados_list'),
    path('deuda/editar/<int:pk>/', DeudaUpdateView.as_view(), name='deuda_editar'),
    path('deuda/toggle-edicion/<int:pk>/', toggle_edicion_deuda, name='toggle_edicion_deuda'),
    path('acuerdos/', AcuerdoPagoListView.as_view(), name='acuerdo_pago_list'),
    path('cuota/<int:cuota_pk>/acuerdo/crear/', AcuerdoPagoCreateView.as_view(), name='acuerdo_pago_create'),
    path('acuerdo/<int:pk>/editar/', AcuerdoPagoUpdateView.as_view(), name='acuerdo_pago_update'),
    path('retirados/pdf/', generar_pdf_retirados_view, name='generar_pdf_retirados'),
]