from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.template.loader import render_to_string
from datetime import timedelta
from django.utils import timezone

from cartera.models import Cuota


class ProximosPagosListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
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
    model = Cuota
    template_name = 'cartera/proximos_pagos_list.html'
    context_object_name = 'cuotas'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            estado='emitida',
            fecha_vencimiento__gte=timezone.localtime(timezone.now()).date(),
            deuda__alumno__estado='activo'  # Solo alumnos activos
        ).select_related('deuda', 'deuda__alumno')
        
        user = self.request.user
        # Filtrado por rol
        if user.is_superuser:
            municipio_id = self.request.GET.get('municipio')
            if municipio_id:
                queryset = queryset.filter(deuda__alumno__municipio_id=municipio_id)
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                queryset = queryset.filter(deuda__alumno__municipio__departamento=user.departamento)
                municipio_id = self.request.GET.get('municipio')
                if municipio_id:
                    queryset = queryset.filter(deuda__alumno__municipio_id=municipio_id)
        elif getattr(user, 'is_observador', False):
            if hasattr(user, 'sede') and user.sede:
                queryset = queryset.filter(deuda__alumno__grupo_actual__salon__sede=user.sede)
        else:
            # Otro personal (staff) ve solo su municipio
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(deuda__alumno__municipio=user.municipio)

        # Aplicar filtros
        dias_filtro = self.request.GET.get('dias_filtro', 'todos')
        identificacion = self.request.GET.get('identificacion', '')
        apellido = self.request.GET.get('apellido', '')

        if dias_filtro != 'todos':
            dias = dias_filtro.split('-')
            if len(dias) == 1:  # Caso de '90+'
                queryset = queryset.filter(
                    fecha_vencimiento__lte=timezone.localtime(timezone.now()).date() + timedelta(days=int(dias[0]))
                )
            else:
                min_dias = int(dias[0])
                max_dias = int(dias[1])
                queryset = queryset.filter(
                    fecha_vencimiento__gte=timezone.localtime(timezone.now()).date() + timedelta(days=min_dias),
                    fecha_vencimiento__lte=timezone.localtime(timezone.now()).date() + timedelta(days=max_dias)
                )

        if identificacion:
            queryset = queryset.filter(deuda__alumno__identificacion__icontains=identificacion)

        if apellido:
            queryset = queryset.filter(
                Q(deuda__alumno__primer_apellido__icontains=apellido) |
                Q(deuda__alumno__segundo_apellido__icontains=apellido)
            )

        # Ordenar por fecha de vencimiento (equivalente a días restantes ascendente)
        queryset = queryset.order_by('fecha_vencimiento')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar el mensaje preformateado y días restantes a cada cuota
        for cuota in context['cuotas']:
            alumno = cuota.deuda.alumno
            
            # Renderizar el mensaje con los datos actuales
            message_context = {
                'nombres': alumno.nombres,
                'primer_apellido': alumno.primer_apellido,
                'segundo_apellido': alumno.segundo_apellido,
                'fecha_vencimiento': cuota.fecha_vencimiento,
                'dias_restantes': (cuota.fecha_vencimiento - timezone.localtime(timezone.now()).date()).days,
                'monto': cuota.monto
            }
            
            # Renderizar el template y codificar para URL
            cuota.whatsapp_message = render_to_string(
                'cartera/proximo_pago_template.txt',
                message_context
            ).replace('\n', '%0A').replace(' ', '%20')
        
        for cuota in context['cuotas']:
            cuota.dias_restantes = (cuota.fecha_vencimiento - timezone.localtime(timezone.now()).date()).days
        
        # Añadir información de paginación al contexto
        if context.get('is_paginated', False):
            paginator = context['paginator']
            page_obj = context['page_obj']
            
            # Obtener el número de página actual
            page_number = page_obj.number
            
            # Calcular el rango de páginas a mostrar
            page_range = list(paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1))
            context['page_range'] = page_range
        
        from ubicaciones.models import Municipio
        user = self.request.user
        # Lógica de contexto por rol
        if user.is_superuser:
            context['municipios'] = Municipio.objects.all().order_by('nombre')
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                context['municipios'] = Municipio.objects.filter(departamento=user.departamento).order_by('nombre')
            else:
                context['municipios'] = Municipio.objects.none()
        
        context['municipio_seleccionado'] = self.request.GET.get('municipio', '')
        context['is_coordinador'] = user.groups.filter(name='CoordinadorDepartamental').exists()
        
        return context