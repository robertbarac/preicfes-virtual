from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q

from academico.models import Alumno


class BecadosListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    def test_func(self):
        return self.request.user.is_staff
    model = Alumno
    template_name = 'cartera/becados_list.html'
    context_object_name = 'becados'
    paginate_by = 20  # Paginación de 2 elementos por página
   
    def get_queryset(self):
        queryset = Alumno.objects.filter(
            es_becado=True
        ).select_related(
            'grupo_actual__salon',
            'grupo_actual__salon__sede',
            'grupo_actual__salon__sede__municipio'
        )
        
        user = self.request.user
        # Filtrado por rol
        if user.is_superuser:
            municipio_id = self.request.GET.get('municipio')
            if municipio_id:
                queryset = queryset.filter(municipio_id=municipio_id)
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                queryset = queryset.filter(municipio__departamento=user.departamento)
                municipio_id = self.request.GET.get('municipio')
                if municipio_id:
                    queryset = queryset.filter(municipio_id=municipio_id)
        else:
            # Otro personal (staff) ve solo su municipio
            queryset = queryset.filter(municipio=user.municipio)
                
        # Filtrar por tipo de programa
        tipo_programa = self.request.GET.get('tipo_programa')
        if tipo_programa:
            queryset = queryset.filter(tipo_programa=tipo_programa)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_becados'] = self.get_queryset().count()
        
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
        
        context['selected_municipio'] = self.request.GET.get('municipio', '')
        context['is_coordinador'] = user.groups.filter(name='CoordinadorDepartamental').exists()
            
        # Añadir tipos de programa al contexto
        context['tipos_programa'] = dict(Alumno.TIPO_PROGRAMA)
        context['tipo_programa_seleccionado'] = self.request.GET.get('tipo_programa', '')
        
        # Añadir información de paginación al contexto
        if context.get('is_paginated', False):
            paginator = context['paginator']
            page_obj = context['page_obj']
            
            # Obtener el número de página actual
            page_number = page_obj.number
            
            # Calcular el rango de páginas a mostrar
            page_range = list(paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1))
            context['page_range'] = page_range
            
        return context