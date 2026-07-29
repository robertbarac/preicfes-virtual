from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string

from cartera.models import Cuota

def make_accent_insensitive_regex(term):
    mapping = {
        'a': '[aáAÁ]', 'e': '[eéEÉ]', 'i': '[iíIÍ]', 'o': '[oóOÓ]', 'u': '[uúUÚ]',
        'n': '[nñNÑ]', 'A': '[aáAÁ]', 'E': '[eéEÉ]', 'I': '[iíIÍ]', 'O': '[oóOÓ]',
        'U': '[uúUÚ]', 'N': '[nñNÑ]', 'á': '[aáAÁ]', 'é': '[eéEÉ]', 'í': '[iíIÍ]',
        'ó': '[oóOÓ]', 'ú': '[uúUÚ]', 'ñ': '[nñNÑ]', 'Á': '[aáAÁ]', 'É': '[eéEÉ]',
        'Í': '[iíIÍ]', 'Ó': '[oóOÓ]', 'Ú': '[uúUÚ]', 'Ñ': '[nñNÑ]'
    }
    regex_str = ''
    for char in term:
        if char in mapping:
            regex_str += mapping[char]
        elif char.isalnum() or char.isspace():
            regex_str += char
        else:
            regex_str += '\\' + char
    return regex_str


class CuotasVencidasListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Cuota
    template_name = 'cartera/cuotas_vencidas_list.html'
    context_object_name = 'cuotas'
    paginate_by = 20

    def test_func(self):
        user = self.request.user
        if getattr(user, 'is_observador', False):
            return True
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

        queryset = super().get_queryset().filter(
            estado__in=['emitida', 'vencida'],  # Excluir 'pagada_parcial'
            fecha_vencimiento__lt=timezone.localtime(timezone.now()),
            deuda__alumno__estado='activo'  # Solo alumnos activos
        ).select_related('deuda', 'deuda__alumno', 'deuda__alumno__municipio')

        user = self.request.user
        municipio_id = self.request.GET.get('municipio')
        departamento_id = self.request.GET.get('departamento')
        sede_id = self.request.GET.get('sede')

        # Filtrado por rol base y parámetros de ubicación
        if user.is_superuser:
            if departamento_id:
                queryset = queryset.filter(deuda__alumno__municipio__departamento_id=departamento_id)
            if municipio_id:
                queryset = queryset.filter(deuda__alumno__municipio_id=municipio_id)
            if sede_id:
                queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede_id=sede_id)
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                queryset = queryset.filter(deuda__alumno__municipio__departamento=user.departamento)
            if municipio_id:
                queryset = queryset.filter(deuda__alumno__municipio_id=municipio_id)
            if sede_id:
                queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede_id=sede_id)
        elif getattr(user, 'is_observador', False):
            if hasattr(user, 'sede') and user.sede:
                queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede=user.sede)
        else:
            # Otro personal (staff) ve solo su municipio
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(deuda__alumno__municipio=user.municipio)
            if sede_id:
                queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede_id=sede_id)

        # Aplicar filtros
        dias_filtro = self.request.GET.get('dias_filtro', 'todos')
        identificacion = self.request.GET.get('identificacion', '')
        buscador = self.request.GET.get('buscador', '')

        if dias_filtro != 'todos':
            dias = dias_filtro.split('-')
            if len(dias) == 1:  # Caso de '90+'
                queryset = queryset.filter(
                    fecha_vencimiento__lt=timezone.localtime(timezone.now()) - timedelta(days=int(dias[0]))
                )
            else:
                min_dias = int(dias[0])
                max_dias = int(dias[1])
                queryset = queryset.filter(
                    fecha_vencimiento__lt=timezone.localtime(timezone.now()) - timedelta(days=min_dias),
                    fecha_vencimiento__gte=timezone.localtime(timezone.now()) - timedelta(days=max_dias)
                )

        if identificacion:
            queryset = queryset.filter(deuda__alumno__identificacion__icontains=identificacion)

        # Filtrar por deuda pendiente
        deuda_pendiente = self.request.GET.get('deuda_pendiente', '')
        if deuda_pendiente:
            if deuda_pendiente == '0-100k':
                queryset = queryset.filter(deuda__saldo_pendiente__lte=100000)
            elif deuda_pendiente == '101k-200k':
                queryset = queryset.filter(deuda__saldo_pendiente__gt=100000, deuda__saldo_pendiente__lte=200000)
            elif deuda_pendiente == '201k-300k':
                queryset = queryset.filter(deuda__saldo_pendiente__gt=200000, deuda__saldo_pendiente__lte=300000)
            elif deuda_pendiente == '301k-500k':
                queryset = queryset.filter(deuda__saldo_pendiente__gt=300000, deuda__saldo_pendiente__lte=500000)
            elif deuda_pendiente == '500k+':
                queryset = queryset.filter(deuda__saldo_pendiente__gt=500000)

        if buscador:
            # Separamos las palabras para simular la búsqueda del admin de Django
            for term in buscador.split():
                regex_term = make_accent_insensitive_regex(term)
                queryset = queryset.filter(
                    Q(deuda__alumno__nombres__iregex=regex_term) |
                    Q(deuda__alumno__primer_apellido__iregex=regex_term) |
                    Q(deuda__alumno__segundo_apellido__iregex=regex_term)
                )

        # Aplicar ordenamiento por días de atraso (días de atraso = hoy - fecha_vencimiento)
        # orden 'asc' => menos días de atraso => fecha_vencimiento más reciente (desc)
        # orden 'desc' => más días de atraso => fecha_vencimiento más antigua (asc)
        orden = self.request.GET.get('orden', 'desc')  # Por defecto descendente
        if orden == 'asc':
            queryset = queryset.order_by('-fecha_vencimiento')
        else:
            queryset = queryset.order_by('fecha_vencimiento')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.localtime(timezone.now()).date()
        
        # Obtener estadísticas de cuotas vencidas agrupadas por alumno
        overdue_stats = Cuota.objects.filter(
            estado__in=['emitida', 'vencida'],
            fecha_vencimiento__lt=today,
            deuda__alumno__estado='activo'
        ).values('deuda__alumno_id').annotate(
            total_vencidas_count=Count('id'),
            total_vencidas_monto=Sum('monto')
        )
        
        stats_dict = {
            item['deuda__alumno_id']: {
                'count': item['total_vencidas_count'],
                'monto': item['total_vencidas_monto']
            }
            for item in overdue_stats
        }
        
        # Agregar el mensaje preformateado y días de atraso a cada cuota
        for cuota in context['cuotas']:
            alumno = cuota.deuda.alumno
            cuota.dias_atraso = (timezone.localtime(timezone.now()).date() - cuota.fecha_vencimiento).days
            
            # Obtener estadísticas del alumno
            stats = stats_dict.get(alumno.id, {'count': 0, 'monto': 0})
            cuota.total_vencidas_count = stats['count']
            cuota.total_vencidas_monto = stats['monto']

            # Renderizar el mensaje con los datos actuales
            message_context = {
                'nombres': alumno.nombres,
                'primer_apellido': alumno.primer_apellido,
                'segundo_apellido': alumno.segundo_apellido,
                'fecha_vencimiento': cuota.fecha_vencimiento,
                'dias_atraso': cuota.dias_atraso,
                'monto': cuota.monto,
                'monto_abonado': cuota.monto_abonado,
                'saldo_pendiente': cuota.deuda.saldo_pendiente
            }
            
            # Renderizar el template y codificar para URL
            cuota.whatsapp_message = render_to_string(
                'cartera/whatsapp_message_template.txt',
                message_context
            ).replace('\n', '%0A').replace(' ', '%20')
        
        # Agregar filtros al contexto
        # Obtener parámetros GET actuales para query_string
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']

        context.update({
            'dias_filtro': self.request.GET.get('dias_filtro', 'todos'),
            'identificacion': self.request.GET.get('identificacion', ''),
            'buscador': self.request.GET.get('buscador', ''),
            'orden': self.request.GET.get('orden', 'desc'),
            'deuda_pendiente': self.request.GET.get('deuda_pendiente', ''),
            'query_string': get_params.urlencode()
        })
        
        from ubicaciones.models import Municipio, Departamento, Sede
        user = self.request.user
        
        departamento_id = self.request.GET.get('departamento')
        municipio_id = self.request.GET.get('municipio')
        sede_id = self.request.GET.get('sede')

        sedes_qs = Sede.objects.all().order_by('nombre')
        
        # Lógica de contexto por rol
        if user.is_superuser:
            context['departamentos'] = Departamento.objects.all().order_by('nombre')
            context['municipios'] = Municipio.objects.all().order_by('nombre')
            if departamento_id:
                context['municipios'] = context['municipios'].filter(departamento_id=departamento_id)
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                context['municipios'] = Municipio.objects.filter(departamento=user.departamento).order_by('nombre')
            else:
                context['municipios'] = Municipio.objects.none()
        else:
            if hasattr(user, 'municipio') and user.municipio:
                sedes_qs = sedes_qs.filter(municipio=user.municipio)

        if municipio_id:
            sedes_qs = sedes_qs.filter(municipio_id=municipio_id)
        elif departamento_id:
            sedes_qs = sedes_qs.filter(municipio__departamento_id=departamento_id)
        elif user.groups.filter(name='CoordinadorDepartamental').exists() and hasattr(user, 'departamento') and user.departamento:
            sedes_qs = sedes_qs.filter(municipio__departamento=user.departamento)
        elif getattr(user, 'is_observador', False) and hasattr(user, 'sede') and user.sede:
            sedes_qs = sedes_qs.filter(id=user.sede.id)

        context['sedes'] = sedes_qs
        context['departamento_seleccionado'] = int(departamento_id) if departamento_id else None
        context['municipio_seleccionado'] = int(municipio_id) if municipio_id else None
        context['sede_seleccionada'] = int(sede_id) if sede_id else None
        
        context['is_coordinador'] = user.groups.filter(name='CoordinadorDepartamental').exists()
        
        return context