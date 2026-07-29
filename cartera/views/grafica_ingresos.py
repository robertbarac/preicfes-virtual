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
from decimal import Decimal

from cartera.models import Cuota, Egreso
from academico.models import Alumno
from ubicaciones.models import Departamento, Municipio


class GraficaIngresosView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):

    template_name = 'cartera/grafica_ingresos.html'

    def test_func(self):
        user = self.request.user
        # Un usuario puede ver la página si es superuser o si tiene el permiso para ver cuotas.
        # user.is_superuser or 
        return user.has_perm('cartera.view_cuota')

    def dispatch(self, request, *args, **kwargs):
        if not self.test_func():
            return HttpResponseForbidden("No tienes permisos para ver esta página.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        año_actual = timezone.localtime(timezone.now()).year

        # Unificar año seleccionado desde el filtro de cumplimiento
        año_seleccionado = int(self.request.GET.get('año_cumplimiento', año_actual))
        context['año_seleccionado'] = año_seleccionado

        # Obtener el año y mes seleccionados para el cumplimiento
        año_cumplimiento = int(self.request.GET.get('año_cumplimiento', año_actual))
        mes_cumplimiento = int(self.request.GET.get('mes_cumplimiento', timezone.now().month))

        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        tipo_programa = self.request.GET.get('tipo_programa')

        # --- Lógica de Filtros por Rol ---
        user = self.request.user
        is_coordinador = user.groups.filter(name='CoordinadorDepartamental').exists()
        is_auxiliar = user.groups.filter(name='Auxiliar').exists()

        cuotas_qs = Cuota.objects.all()
        departamentos_qs = Departamento.objects.none()
        municipios_qs = Municipio.objects.none()

        if user.is_superuser:
            departamentos_qs = Departamento.objects.all()
            municipios_qs = Municipio.objects.all()
            if departamento_id:
                municipios_qs = municipios_qs.filter(departamento_id=departamento_id)

            if municipio_id:
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id)
            elif departamento_id:
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio__departamento_id=departamento_id)

        elif is_coordinador or is_auxiliar:
            if hasattr(user, 'departamento') and user.departamento:
                departamentos_qs = Departamento.objects.filter(id=user.departamento.id)
                municipios_qs = Municipio.objects.filter(departamento=user.departamento)
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio__departamento=user.departamento)

                # Si se selecciona un municipio específico, se prioriza ese filtro
                if municipio_id:
                    cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id)
        
        if tipo_programa:
            cuotas_qs = cuotas_qs.filter(deuda__alumno__tipo_programa=tipo_programa)

        context['departamentos'] = departamentos_qs
        context['departamento_seleccionado'] = int(departamento_id) if departamento_id else None
        context['municipios'] = municipios_qs
        context['municipio_seleccionado'] = int(municipio_id) if municipio_id else None
        context['is_coordinador_or_auxiliar'] = is_coordinador or is_auxiliar

        # Obtener los años disponibles para la gráfica (basado en cuándo se realizaron los pagos)
        # Primero intentamos obtener años de fecha_pago (para pagos ya realizados)
        años_pago = list(cuotas_qs.filter(fecha_pago__isnull=False).dates('fecha_pago', 'year').values_list('fecha_pago__year', flat=True))
        # Luego añadimos años de fecha_vencimiento (para pagos futuros)
        años_vencimiento = list(cuotas_qs.dates('fecha_vencimiento', 'year').values_list('fecha_vencimiento__year', flat=True))
        años_grafica = list(set(años_pago + años_vencimiento))
        if not años_grafica or año_actual not in años_grafica:
            años_grafica.append(año_actual)
        años_grafica = sorted(set(años_grafica))

        # Los años de cumplimiento son los mismos que los de la gráfica
        años_cumplimiento = años_grafica

        # La meta mensual es la suma de todas las cuotas del mes de alumnos activos
        meta_mensual = cuotas_qs.filter(
            fecha_vencimiento__year=año_cumplimiento,
            fecha_vencimiento__month=mes_cumplimiento,
            deuda__alumno__estado='activo'
        ).aggregate(total=Sum('monto'))['total'] or 0

        # Obtener los ingresos del mes (basado en cuándo se realizaron los pagos realmente)
        ingresos_mes = cuotas_qs.filter(
            fecha_pago__year=año_cumplimiento,
            fecha_pago__month=mes_cumplimiento,
            monto_abonado__gt=0
        ).aggregate(total=Sum('monto_abonado'))['total'] or 0

        # Calcular el porcentaje de cumplimiento
        porcentaje_cumplimiento = (ingresos_mes / meta_mensual * 100) if meta_mensual > 0 else 0

        # Calcular superávit o déficit
        superavit_deficit = ingresos_mes - meta_mensual

        # Calcular umbrales para la etiqueta <meter>
        meter_low = meta_mensual * Decimal('0.80')
        meter_high = meta_mensual * Decimal('1.0')

        context.update({
            'año_seleccionado': año_seleccionado,
            'años_grafica': años_grafica,
            'año_cumplimiento': año_cumplimiento,
            'años_cumplimiento': años_cumplimiento,
            'mes_cumplimiento': mes_cumplimiento,
            'meses': [(i, month_name[i]) for i in range(1, 13)],
            'nombre_mes': month_name[mes_cumplimiento],
            'meta_mensual': meta_mensual,
            'ingresos_mes': ingresos_mes,
            'porcentaje_cumplimiento': porcentaje_cumplimiento,
            'superavit_deficit': superavit_deficit,
            'meter_low': meter_low,
            'meter_high': meter_high,
            'tipos_programa': dict(Alumno.TIPO_PROGRAMA),
            'tipo_programa_seleccionado': tipo_programa
        })
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if 'grafica' in request.GET:
            return self.generar_grafica(context)
        return self.render_to_response(context)


    def generar_grafica(self, context):
        año_seleccionado = int(self.request.GET.get('año', timezone.localtime(timezone.now()).year))

        # Obtener departamento y municipio seleccionados
        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')

        tipo_programa = self.request.GET.get('tipo_programa')

        # --- Lógica de Filtros por Rol ---
        user = self.request.user
        is_coordinador = user.groups.filter(name='CoordinadorDepartamental').exists()
        is_auxiliar = user.groups.filter(name='Auxiliar').exists()

        cuotas_qs = Cuota.objects.filter(
            fecha_pago__year=año_seleccionado,
            monto_abonado__gt=0
        )

        if user.is_superuser:
            if municipio_id:
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id)
            elif departamento_id:
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio__departamento_id=departamento_id)

        elif is_coordinador or is_auxiliar:
            if hasattr(user, 'departamento') and user.departamento:
                cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio__departamento=user.departamento)
                # Si además se especifica un municipio, se añade ese filtro
                if municipio_id:
                    cuotas_qs = cuotas_qs.filter(deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id)
        
        if tipo_programa:
            cuotas_qs = cuotas_qs.filter(deuda__alumno__tipo_programa=tipo_programa)

        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        ingresos = [0] * 12

        # Agrupar cuotas por mes - usando el mes de pago real
        cuotas = cuotas_qs.values('fecha_pago__month').annotate(
            total_abonado=Sum('monto_abonado')
        )

        for cuota in cuotas:
            ingresos[cuota['fecha_pago__month'] - 1] = float(cuota['total_abonado'] or 0)

        # Ya no consultamos egresos en esta vista

        # Configuración de la gráfica de barras
        plt.figure(figsize=(12, 6))
        index = np.arange(len(meses))
        bar_width = 0.6

        # Gráfica de barras solo para ingresos
        barra_ingresos = plt.bar(index, ingresos, bar_width, label='Ingresos', color='#4CAF50')

        # Mostrar valores en la parte superior de las barras
        for barra in barra_ingresos:
            altura = barra.get_height()
            plt.text(barra.get_x() + barra.get_width() / 2, altura, f'${altura:,.0f}', ha='center', va='bottom', fontsize=10, color='black')

        # Configuración final de la gráfica
        plt.xlabel('Meses')
        plt.ylabel('Valor ($)')
        plt.title(f'Ingresos - {año_seleccionado}')
        plt.xticks(index, meses)
        plt.legend()
        plt.tight_layout()

        # Guardar la gráfica en un buffer para mostrarla en el template
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        plt.close()
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'inline; filename=grafica_{año_seleccionado}.png'
        return response