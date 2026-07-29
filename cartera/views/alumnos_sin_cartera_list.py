# views/alumnos_sin_cartera_list.py

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q

from academico.models import Alumno


class AlumnosSinCarteraListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vista detallada para listar todos los alumnos activos que no tienen Deuda o Cuotas generadas.
    Accesible para Superusuarios y Staff autorizado.
    """
    model = Alumno
    template_name = 'cartera/alumnos_sin_cartera_list.html'
    context_object_name = 'alumnos'
    paginate_by = 30

    def test_func(self):
        return self.request.user.has_perm('cartera.change_cuota')

    def get_queryset(self):
        return Alumno.objects.filter(
            estado='activo'
        ).filter(
            Q(deuda__isnull=True) | Q(deuda__cuotas__isnull=True)
        ).distinct().select_related('grupo_actual', 'municipio', 'deuda', 'vendedor').order_by('-fecha_ingreso', 'primer_apellido')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Alerta Temprana: Alumnos sin Cartera Organizada'
        
        alumnos_pagina = context.get('alumnos', [])
        if alumnos_pagina:
            from django.contrib.admin.models import LogEntry, ADDITION
            from django.contrib.contenttypes.models import ContentType
            
            ct_alumno = ContentType.objects.get_for_model(Alumno)
            object_ids = [str(a.id) for a in alumnos_pagina]
            
            # 1. LogEntry de creación
            logs_add = LogEntry.objects.filter(
                content_type=ct_alumno,
                action_flag=ADDITION,
                object_id__in=object_ids
            ).select_related('user')
            log_map_add = {l.object_id: l.user.get_full_name().strip() or l.user.username for l in logs_add}

            # 2. LogEntry de edición (fallback)
            logs_any = LogEntry.objects.filter(
                content_type=ct_alumno,
                object_id__in=object_ids
            ).order_by('id').select_related('user')
            log_map_any = {}
            for l in logs_any:
                if l.object_id not in log_map_any:
                    log_map_any[l.object_id] = l.user.get_full_name().strip() or l.user.username

            for a in alumnos_pagina:
                sid = str(a.id)
                if sid in log_map_add:
                    a.creador_nombre = log_map_add[sid]
                elif a.vendedor:
                    a.creador_nombre = str(a.vendedor)
                elif sid in log_map_any:
                    a.creador_nombre = log_map_any[sid]
                else:
                    a.creador_nombre = 'Sin Registro (Histórico)'
                
        return context
