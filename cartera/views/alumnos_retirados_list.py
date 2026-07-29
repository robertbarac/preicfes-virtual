from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.utils import timezone
from academico.models import Alumno
from ubicaciones.models import Municipio, Departamento

class AlumnosRetiradosListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Alumno
    template_name = 'cartera/alumnos_retirados_list.html'
    context_object_name = 'alumnos'
    paginate_by = 25

    def test_func(self):
        user = self.request.user
        if not user.is_staff:
            return False

        if user.is_superuser:
            return True

        grupos_autorizados = [
            'Cartera',
            'SecretariaCartera',
            'Auxiliar',
            'CoordinadorDepartamental',
        ]

        return user.groups.filter(name__in=grupos_autorizados).exists()


    def get_queryset(self):
        # Aseguramos que todos los alumnos retirados tienen fecha_retiro no nula
        queryset = Alumno.objects.filter(estado='retirado', fecha_retiro__isnull=False).select_related(
            'grupo_actual__salon__sede__municipio__departamento', 'deuda'
        )

        user = self.request.user
        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        tipo_programa = self.request.GET.get('tipo_programa')

        # Lógica de filtros por rol
        if user.is_superuser:
            if departamento_id:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento_id=departamento_id)
            if municipio_id:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
        elif user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            if hasattr(user, 'departamento') and user.departamento:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento=user.departamento)
                if municipio_id:
                    queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
            else:
                queryset = queryset.none()
        else: # Otros roles de staff
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio=user.municipio)
            else:
                queryset = queryset.none()

        # Filtros adicionales
        # Aplicar filtros de fecha de retiro de forma independiente
        if mes:
            try:
                mes_int = int(mes)
                queryset = queryset.filter(fecha_retiro__month=mes_int)
            except (ValueError, TypeError):
                # Si mes no es un entero válido, ignorar el filtro
                pass
                
        if anio:
            try:
                anio_int = int(anio)
                queryset = queryset.filter(fecha_retiro__year=anio_int)
            except (ValueError, TypeError):
                # Si año no es un entero válido, ignorar el filtro
                pass
            
        # Filtro por tipo de programa
        if tipo_programa:
            queryset = queryset.filter(tipo_programa=tipo_programa)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        departamento_id = self.request.GET.get('departamento')

        # Totales y estadísticas
        queryset = self.get_queryset() # Usar el queryset ya filtrado para los cálculos
        context['total_retirados'] = queryset.count()
        context['total_saldo_pendiente'] = queryset.filter(deuda__estado='emitida').aggregate(Sum('deuda__saldo_pendiente'))['deuda__saldo_pendiente__sum'] or 0

        # Contexto para filtros
        context['is_coordinador_or_auxiliar'] = user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()
        if user.is_superuser:
            context['departamentos'] = Departamento.objects.all()
            municipios_qs = Municipio.objects.all()
            if departamento_id:
                municipios_qs = municipios_qs.filter(departamento_id=departamento_id)
            context['municipios'] = municipios_qs
        elif context['is_coordinador_or_auxiliar']:
            if hasattr(user, 'departamento') and user.departamento:
                context['municipios'] = Municipio.objects.filter(departamento=user.departamento)

        # Años para el filtro
        anio_actual = timezone.localtime(timezone.now()).year
        context['anios'] = range(anio_actual - 5, anio_actual + 2)

        # Valores seleccionados para mantener en los filtros
        context['departamento_seleccionado'] = self.request.GET.get('departamento')
        context['municipio_seleccionado'] = self.request.GET.get('municipio')
        context['mes_seleccionado'] = self.request.GET.get('mes')
        context['anio_seleccionado'] = self.request.GET.get('anio')
        context['tipo_programa_seleccionado'] = self.request.GET.get('tipo_programa')
        
        # Convertir tipos_programa de tupla a dict para usar en el template
        context['tipos_programa'] = dict(Alumno.TIPO_PROGRAMA)
        
        # Preparar string de parámetros para URLs de paginación
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            get_params.pop('page')
        context['params'] = get_params.urlencode() + '&' if get_params else ''
        
        return context
