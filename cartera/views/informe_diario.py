from cartera.models.deuda import Deuda
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.db.models import Sum
from django.utils import timezone
from django.utils.formats import date_format

from cartera.models import Cuota
from ubicaciones.models import Municipio, Departamento, Sede
from academico.models import Alumno


class InformeDiarioView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    def test_func(self):
        # Permitir acceso a superusers o a quienes tengan el permiso para ver el informe diario.
        if getattr(self.request.user, 'is_observador', False):
            return True
        return self.request.user.is_superuser or self.request.user.has_perm('cartera.view_cuota')
    template_name = 'cartera/informe_diario.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener fecha del filtro o usar la actual
        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            fecha_seleccionada = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha_seleccionada = timezone.localtime(timezone.now()).date()
        
        context['fecha_seleccionada'] = fecha_seleccionada.strftime('%Y-%m-%d')
        
        # Obtener departamento seleccionado (solo para superusuarios)
        departamento_id = self.request.GET.get('departamento')
        
        # Obtener municipio seleccionado
        municipio_id = self.request.GET.get('municipio')
        
        # Obtener sede seleccionada
        sede_id = self.request.GET.get('sede')
        
        # Lógica de permisos y filtros de ubicación
        user = self.request.user
        is_coordinador_or_auxiliar = user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()

        if user.is_superuser:
            # Superuser puede ver y filtrar todo.
            pass
        elif is_coordinador_or_auxiliar:
            # Coordinador/Auxiliar ve su departamento. Puede filtrar por municipio dentro de él.
            if hasattr(user, 'departamento') and user.departamento:
                departamento_id = user.departamento.id
            else:
                context['warning_message'] = 'No tienes un departamento asignado. Contacta al administrador.'
                departamento_id = None # Forzar a no ver nada si no tiene depto.
        elif getattr(user, 'is_observador', False):
            # ObservadorColegio ve solo su sede
            if hasattr(user, 'sede') and user.sede:
                sede_id = user.sede.id
                municipio_id = None
                departamento_id = None
            else:
                context['warning_message'] = 'No tienes una sede asignada. Contacta al administrador.'
                sede_id = None
                municipio_id = None
                departamento_id = None
        else:
            # Otros roles (ej. Secretaria) ven solo su municipio.
            if hasattr(user, 'municipio') and user.municipio:
                municipio_id = user.municipio.id
                departamento_id = None
            else:
                context['warning_message'] = 'No tienes un municipio asignado. Contacta al administrador.'
                municipio_id = None # Forzar a no ver nada si no tiene municipio.
            
        # Obtener tipo de programa seleccionado
        tipo_programa = self.request.GET.get('tipo_programa')
        
        # Obtener filtros de culminación (rango)
        mes_ini = self.request.GET.get('mes_culminacion_inicio')
        ano_ini = self.request.GET.get('ano_culminacion_inicio')
        mes_fin = self.request.GET.get('mes_culminacion_fin')
        ano_fin = self.request.GET.get('ano_culminacion_fin')
        
        import datetime
        import calendar
        
        fecha_limite_inicio = None
        if ano_ini:
            m_i = int(mes_ini) if mes_ini else 1
            fecha_limite_inicio = datetime.date(int(ano_ini), m_i, 1)
            
        fecha_limite_fin = None
        if ano_fin:
            m_f = int(mes_fin) if mes_fin else 12
            last_day = calendar.monthrange(int(ano_fin), m_f)[1]
            fecha_limite_fin = datetime.date(int(ano_fin), m_f, last_day)
        
        # Obtener listas para filtros según permisos
        context['is_coordinador_or_auxiliar'] = is_coordinador_or_auxiliar
        
        # Inicializar listas
        sedes_qs = Sede.objects.all()

        if user.is_superuser:
            context['departamentos'] = Departamento.objects.all()
            context['municipios'] = Municipio.objects.all()
            if departamento_id:
                context['municipios'] = context['municipios'].filter(departamento_id=departamento_id)
        elif is_coordinador_or_auxiliar:
            if hasattr(user, 'departamento') and user.departamento:
                context['municipios'] = Municipio.objects.filter(departamento=user.departamento)
        
        # Filtrar sedes disponibles basado en municipio/departamento
        if municipio_id:
            sedes_qs = sedes_qs.filter(municipio_id=municipio_id)
        elif departamento_id:
            sedes_qs = sedes_qs.filter(municipio__departamento_id=departamento_id)
        
        context['sedes'] = sedes_qs

        context['departamento_seleccionado'] = int(departamento_id) if departamento_id else None
        context['municipio_seleccionado'] = int(municipio_id) if municipio_id else None
        context['sede_seleccionada'] = int(sede_id) if sede_id else None
        
        # Obtener lista de tipos de programa para el filtro
        context['tipos_programa'] = dict(Alumno.TIPO_PROGRAMA)
        context['tipo_programa_seleccionado'] = tipo_programa
        
        # Agregar meses y años de culminación para los filtros
        context['meses_anio'] = [
            ('1', 'Enero'),
            ('2', 'Febrero'),
            ('3', 'Marzo'),
            ('4', 'Abril'),
            ('5', 'Mayo'),
            ('6', 'Junio'),
            ('7', 'Julio'),
            ('8', 'Agosto'),
            ('9', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ]
        
        import datetime
        current_year = datetime.date.today().year
        # Obtener los años presentes en la base de datos para fecha_culminacion
        years = Alumno.objects.exclude(fecha_culminacion__isnull=True).dates('fecha_culminacion', 'year')
        years_list = sorted(list(set(y.year for y in years)))
        if not years_list:
            years_list = [current_year - 1, current_year, current_year + 1]
            
        context['years_culminacion'] = [str(y) for y in years_list]
        context['mes_culminacion_inicio_seleccionado'] = mes_ini or ''
        context['ano_culminacion_inicio_seleccionado'] = ano_ini or ''
        context['mes_culminacion_fin_seleccionado'] = mes_fin or ''
        context['ano_culminacion_fin_seleccionado'] = ano_fin or ''
            
        # Base queryset para cuotas
        cuotas_qs = Cuota.objects.all()
        
        # Filtrar por departamento
        if departamento_id:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede__municipio__departamento_id=departamento_id
            )
        
        # Filtrar por municipio
        if municipio_id:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id
            )
        
        # Filtrar por sede
        if sede_id:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede_id=sede_id
            )
            
        # Filtrar por tipo de programa
        if tipo_programa:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__tipo_programa=tipo_programa
            )
            
        # Filtrar por rango de fecha de culminación
        if fecha_limite_inicio:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__fecha_culminacion__gte=fecha_limite_inicio
            )
        if fecha_limite_fin:
            cuotas_qs = cuotas_qs.filter(
                deuda__alumno__fecha_culminacion__lte=fecha_limite_fin
            )
        
        # Datos de recaudación del día (basado en la fecha de pago seleccionada)
        cuotas_hoy = cuotas_qs.filter(
            fecha_pago=fecha_seleccionada,
            monto_abonado__gt=0
        )
        
        # Totales por método de pago
        context['recaudo_efectivo'] = cuotas_hoy.filter(
            metodo_pago='efectivo'
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0
        
        context['recaudo_transferencia'] = cuotas_hoy.filter(
            metodo_pago='transferencia'
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0
        
        context['recaudo_datáfono'] = cuotas_hoy.filter(
            metodo_pago='datáfono'
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0

        context['recaudo_no_especificado'] = cuotas_hoy.filter(
            metodo_pago__isnull=True
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0
        
        context['total_recaudado'] = (
            context['recaudo_efectivo'] + 
            context['recaudo_transferencia'] + 
            context['recaudo_datáfono'] + 
            context['recaudo_no_especificado']
        )
        
        # Objetivo del mes (basado en el mes de la fecha seleccionada)
        mes_actual = fecha_seleccionada.month
        anio_actual = fecha_seleccionada.year
        
        # Calcular el objetivo del mes como la suma de todas las cuotas con vencimiento en el mes actual de alumnos activos
        # Esto sigue usando fecha_vencimiento ya que es el objetivo contractual
        context['objetivo_mes'] = cuotas_qs.filter(
            fecha_vencimiento__month=mes_actual,
            fecha_vencimiento__year=anio_actual,
            deuda__alumno__estado='activo'
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        
        # % de cumplimiento - basado en pagos realizados en el mes actual HASTA LA FECHA SELECCIONADA
        recaudado_mes = cuotas_qs.filter(
            fecha_pago__month=mes_actual,
            fecha_pago__year=anio_actual,
            fecha_pago__lte=fecha_seleccionada,  # <-- ESTA ES LA CORRECCIÓN CLAVE
            monto_abonado__gt=0
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0
        
        # Calcular el porcentaje de cumplimiento
        context['porcentaje_cumplimiento'] = (
            (recaudado_mes / context['objetivo_mes']) * 100 
            if context['objetivo_mes'] > 0 else 0
        )
        
        context['recaudado_mes'] = recaudado_mes
        
        # Reporte de cartera
        # Obtener todas las cuotas sin filtrar por estado
        todas_cuotas_qs = Cuota.objects.all()
        
        # Filtrar por departamento
        if departamento_id:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede__municipio__departamento_id=departamento_id
            )
        
        # Filtrar por municipio
        if municipio_id:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede__municipio_id=municipio_id
            )
        
        # Filtrar por sede
        if sede_id:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__grupo_actual__salon__sede_id=sede_id
            )
            
        # Filtrar por tipo de programa
        if tipo_programa:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__tipo_programa=tipo_programa
            )
            
        # Filtrar por rango de fecha de culminación
        if fecha_limite_inicio:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__fecha_culminacion__gte=fecha_limite_inicio
            )
        if fecha_limite_fin:
            todas_cuotas_qs = todas_cuotas_qs.filter(
                deuda__alumno__fecha_culminacion__lte=fecha_limite_fin
            )
        
        # Construir queryset de Deuda para aplicar filtros, considerando la fecha seleccionada
        deudas_qs = Deuda.objects.filter(
            alumno__estado='activo',
            fecha_creacion__date__lte=fecha_seleccionada
        )

        if departamento_id:
            deudas_qs = deudas_qs.filter(alumno__grupo_actual__salon__sede__municipio__departamento_id=departamento_id)
        
        if municipio_id:
            deudas_qs = deudas_qs.filter(alumno__grupo_actual__salon__sede__municipio_id=municipio_id)

        if sede_id:
            deudas_qs = deudas_qs.filter(alumno__grupo_actual__salon__sede_id=sede_id)

        if tipo_programa:
            deudas_qs = deudas_qs.filter(alumno__tipo_programa=tipo_programa)
            
        if fecha_limite_inicio:
            deudas_qs = deudas_qs.filter(alumno__fecha_culminacion__gte=fecha_limite_inicio)
            
        if fecha_limite_fin:
            deudas_qs = deudas_qs.filter(alumno__fecha_culminacion__lte=fecha_limite_fin)

        # Valor total de cartera (suma de todos los montos de deudas filtradas)
        context['valor_cartera'] = deudas_qs.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        
        # Total cobrado hasta la fecha seleccionada
        context['cobrado'] = todas_cuotas_qs.filter(
            # deuda__alumno__estado='activo',
            fecha_pago__lte=fecha_seleccionada
        ).aggregate(Sum('monto_abonado'))['monto_abonado__sum'] or 0
        
        # Falta por cobrar
        context['falta_cobrar'] = context['valor_cartera'] - context['cobrado']
        
        # Fecha formateada para mostrar en el título
        context['fecha_actual'] = date_format(
            fecha_seleccionada, 
            "l, j \d\e F \d\e Y"
        ).capitalize()
        
        return context