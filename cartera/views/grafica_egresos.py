import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Sum
from django.utils import timezone
from calendar import month_name
from collections import defaultdict
import json

from cartera.models import Egreso
from ubicaciones.models import Departamento, Municipio


class GraficaEgresosView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'cartera/grafica_egresos.html'

    def test_func(self):
        user = self.request.user
        if not user.is_staff:
            return False

        if user.is_superuser or self.request.user.has_perm('cartera.view_egreso'):
            return True

        grupos_autorizados = [
            'Cartera',
            'SecretariaCartera',
            'Auxiliar',
            'CoordinadorDepartamental',
        ]

        return user.groups.filter(name__in=grupos_autorizados).exists()


    def dispatch(self, request, *args, **kwargs):
        if not self.test_func():
            return HttpResponseForbidden("No tienes permisos para ver esta página.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        año_actual = timezone.now().year

        # Obtener el año seleccionado para la gráfica
        año_seleccionado = int(self.request.GET.get('año', año_actual))

        # Obtener el mes seleccionado para detalles
        mes_seleccionado = int(self.request.GET.get('mes', timezone.now().month))

        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        concepto = self.request.GET.get('concepto')

        # --- Lógica de Filtros por Rol ---
        user = self.request.user
        is_coordinador_or_auxiliar = user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()

        egresos_qs = Egreso.objects.filter(fecha__year=año_seleccionado)
        departamentos_qs = Departamento.objects.none()
        municipios_qs = Municipio.objects.none()

        if user.is_superuser:
            departamentos_qs = Departamento.objects.all()
            municipios_qs = Municipio.objects.all()
            if departamento_id:
                municipios_qs = municipios_qs.filter(departamento_id=departamento_id)
                egresos_qs = egresos_qs.filter(municipio__departamento_id=departamento_id)
            
            if municipio_id:
                egresos_qs = egresos_qs.filter(municipio_id=municipio_id)

        elif is_coordinador_or_auxiliar:
            if hasattr(user, 'departamento') and user.departamento:
                departamentos_qs = Departamento.objects.filter(id=user.departamento.id)
                municipios_qs = Municipio.objects.filter(departamento=user.departamento)
                egresos_qs = egresos_qs.filter(municipio__departamento=user.departamento)

                if municipio_id:
                    egresos_qs = egresos_qs.filter(municipio_id=municipio_id)

        if concepto:
            egresos_qs = egresos_qs.filter(concepto=concepto)

        context['departamentos'] = departamentos_qs
        context['municipios'] = municipios_qs
        context['departamento_seleccionado'] = int(departamento_id) if departamento_id else None
        context['municipio_seleccionado'] = int(municipio_id) if municipio_id else None
        context['is_coordinador_or_auxiliar'] = is_coordinador_or_auxiliar

        # Obtener los años disponibles para la gráfica
        años_disponibles = list(Egreso.objects.dates('fecha', 'year').values_list('fecha__year', flat=True))
        if not años_disponibles or año_actual not in años_disponibles:
            años_disponibles.append(año_actual)
        años_disponibles = sorted(set(años_disponibles))

        # Calcular egresos por mes para la gráfica
        egresos_por_mes = egresos_qs.values('fecha__month').annotate(total=Sum('valor'))
        egresos_mensuales = [0] * 12
        for egreso in egresos_por_mes:
            egresos_mensuales[egreso['fecha__month'] - 1] = float(egreso['total'] or 0)
        
        # Calcular egresos por concepto para el mes seleccionado
        egresos_mes = egresos_qs.filter(fecha__month=mes_seleccionado)
        total_mes = egresos_mes.aggregate(total=Sum('valor'))['total'] or 0
        
        egresos_por_concepto = egresos_mes.values('concepto').annotate(total=Sum('valor'))
        detalles_conceptos = []
        
        for egreso in egresos_por_concepto:
            concepto_key = egreso['concepto']
            concepto_display = dict(Egreso.CONCEPTO_CHOICES).get(concepto_key, concepto_key)
            monto = float(egreso['total'] or 0)
            porcentaje = (monto / float(total_mes) * 100) if total_mes > 0 else 0
            
            detalles_conceptos.append({
                'concepto_key': concepto_key,
                'concepto': concepto_display,
                'monto': monto,
                'porcentaje': porcentaje
            })

        context.update({
            'año_seleccionado': año_seleccionado,
            'años_disponibles': años_disponibles,
            'mes_seleccionado': mes_seleccionado,
            'nombre_mes': month_name[mes_seleccionado],
            'meses': [(i, month_name[i]) for i in range(1, 13)],
            'egresos_mensuales': egresos_mensuales,
            'total_egresos_año': sum(egresos_mensuales),
            'total_egresos_mes': total_mes,
            'detalles_conceptos': detalles_conceptos,
            'detalles_conceptos_json': json.dumps(detalles_conceptos),
            'conceptos': Egreso.CONCEPTO_CHOICES,
            'concepto_seleccionado': concepto
        })
        
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if 'grafica' in request.GET:
            return self.generar_grafica(context)
        return self.render_to_response(context)

    def generar_grafica(self, context):
        año_seleccionado = int(self.request.GET.get('año', timezone.now().year))

        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        concepto = self.request.GET.get('concepto')

        # --- Lógica de Filtros por Rol ---
        user = self.request.user
        is_coordinador_or_auxiliar = user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()

        egresos_qs = Egreso.objects.filter(fecha__year=año_seleccionado)

        if user.is_superuser:
            if departamento_id:
                egresos_qs = egresos_qs.filter(municipio__departamento_id=departamento_id)
            if municipio_id:
                egresos_qs = egresos_qs.filter(municipio_id=municipio_id)

        elif is_coordinador_or_auxiliar:
            if hasattr(user, 'departamento') and user.departamento:
                egresos_qs = egresos_qs.filter(municipio__departamento=user.departamento)
                if municipio_id:
                    egresos_qs = egresos_qs.filter(municipio_id=municipio_id)

        if concepto:
            egresos_qs = egresos_qs.filter(concepto=concepto)

        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        egresos = [0] * 12

        # Agrupar egresos por mes
        egresos_por_mes = egresos_qs.values('fecha__month').annotate(total=Sum('valor'))

        for egreso in egresos_por_mes:
            egresos[egreso['fecha__month'] - 1] = float(egreso['total'] or 0)

        # Configuración de la gráfica de barras
        plt.figure(figsize=(12, 6))
        index = np.arange(len(meses))
        bar_width = 0.6

        # Gráfica de barras
        barras = plt.bar(index, egresos, bar_width, color='#F44336')

        # Mostrar valores en la parte superior de las barras
        for barra in barras:
            altura = barra.get_height()
            plt.text(barra.get_x() + barra.get_width() / 2, altura, f'${altura:,.0f}', ha='center', va='bottom', fontsize=10, color='black')

        # Configuración final de la gráfica
        plt.xlabel('Meses')
        plt.ylabel('Valor ($)')
        titulo = f'Egresos - {año_seleccionado}'
        if concepto:
            concepto_display = dict(Egreso.CONCEPTO_CHOICES).get(concepto, concepto)
            titulo += f' - {concepto_display}'
        plt.title(titulo)
        plt.xticks(index, meses)
        plt.tight_layout()

        # Guardar la gráfica en un buffer para mostrarla en el template
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        plt.close()
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'inline; filename=grafica_egresos_{año_seleccionado}.png'
        return response
