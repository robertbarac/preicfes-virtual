from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum
from datetime import datetime
from calendar import month_name

from academico.models import Clase
from usuarios.models import User
from cartera.models import TarifaClase


class ClasesProfesorListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Clase
    template_name = 'academico/clases_profesor_list.html'
    context_object_name = 'clases'
    login_url = 'login'
    paginate_by = 20  # Paginación de 2 elementos por página

    def test_func(self):
        return (
            self.request.user.is_staff or 
            self.request.user.id == int(self.kwargs.get('profesor_id'))
        )

    def get_queryset(self):
        profesor_id = self.kwargs.get('profesor_id')
        mes = self.request.GET.get('mes', datetime.now().month)
        estado = self.request.GET.get('estado', 'vista')
        año = self.request.GET.get('año', datetime.now().year)

        queryset = Clase.objects.filter(
            profesor_id=profesor_id,
            fecha__year=año,
            fecha__month=mes,
            estado=estado
        ).select_related(
            'materia',
            'salon',
            'salon__sede'  
        ).order_by('fecha', 'horario')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profesor_id = self.kwargs.get('profesor_id')
        mes_actual = int(self.request.GET.get('mes', datetime.now().month))
        estado_actual = self.request.GET.get('estado', 'vista')
        año_actual = int(self.request.GET.get('año', datetime.now().year))
        
        profesor = get_object_or_404(User, id=profesor_id)
        materias_profesor = (
            Clase.objects.filter(
                profesor=profesor,
                fecha__year=año_actual,
                fecha__month=mes_actual,
                estado=estado_actual
            )
            .values('materia__nombre')
            .annotate(total=Count('materia'))
            .order_by('-total')
        )
        
        # Calcular puede_registrar_asistencia y valor para cada clase
        clases = context['clases']
        total_valor = 0
        
        for clase in clases:
            clase.puede_registrar = clase.puede_registrar_asistencia(self.request.user)
            
            # Determinar si es fin de semana (5=sábado, 6=domingo)
            dia_semana = clase.fecha.weekday()
            tipo_dia = 1 if dia_semana == 5 else 2 if dia_semana == 6 else 0
            
            # Buscar tarifa aplicable
            try:
                tarifa = TarifaClase.objects.get(tipo_dia=tipo_dia, horario=clase.horario, activa=True)
                clase.valor = tarifa.valor
                # Sumar al total solo si la clase está vista
                if clase.estado == 'vista':
                    total_valor += tarifa.valor
            except TarifaClase.DoesNotExist:
                # Si no hay tarifa específica para ese horario, buscar una genérica para ese día
                try:
                    tarifa = TarifaClase.objects.get(tipo_dia=tipo_dia, horario__isnull=True, activa=True)
                    clase.valor = tarifa.valor
                    # Sumar al total solo si la clase está vista
                    if clase.estado == 'vista':
                        total_valor += tarifa.valor
                except TarifaClase.DoesNotExist:
                    clase.valor = 0
        
        # Añadir información de paginación al contexto
        if context.get('is_paginated', False):
            paginator = context['paginator']
            page_obj = context['page_obj']
            
            # Obtener el número de página actual
            page_number = page_obj.number
            
            # Calcular el rango de páginas a mostrar
            page_range = list(paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1))
            context['page_range'] = page_range

        # Obtener años disponibles (al menos el actual y el anterior/siguiente según datos, o rango fijo)
        # Una estrategia simple: listar años desde 2024 hasta el actual + 1
        año_actual_real = datetime.now().year
        años_disponibles = sorted(list(set(
            [date.year for date in Clase.objects.dates('fecha', 'year')] + [año_actual_real]
        )), reverse=True)

        context.update({
            'profesor': profesor,
            'meses': [
                {'numero': i, 'nombre': month_name[i]} 
                for i in range(1, 13)
            ],
            'estados_clase': [
                {'valor': 'programada', 'nombre': 'Programadas'},
                {'valor': 'vista', 'nombre': 'Vistas'},
                {'valor': 'cancelada', 'nombre': 'Canceladas'}
            ],
            'mes_actual': mes_actual,
            'estado_actual': estado_actual,
            'año_actual': año_actual,
            'años': años_disponibles,
            'materias_profesor': materias_profesor,
            'total_valor': total_valor,
            'titulo': f'Clases {dict(Clase.ESTADO_CLASE).get(estado_actual, "").lower()} de {profesor.get_full_name()} - {month_name[mes_actual]} {año_actual}'
        })
        
        return context