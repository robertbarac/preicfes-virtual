from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.template.loader import render_to_string

from academico.models import Clase, Materia, Alumno
from usuarios.models import User
from ubicaciones.models import Municipio, Sede

class ClaseListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Clase
    template_name = 'academico/clase_list.html'
    context_object_name = 'clases'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = Clase.objects.all()
        
        user = self.request.user
        # Filtrado por rol
        if user.is_superuser:
            pass  # Superuser ve todo
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                queryset = queryset.filter(salon__sede__municipio__departamento=user.departamento)
        else:
            # Otro personal (staff) ve solo su municipio
            queryset = queryset.filter(salon__sede__municipio=user.municipio)
        
        # Filtros
        estado = self.request.GET.get('estado')
        profesor = self.request.GET.get('profesor')
        materia = self.request.GET.get('materia')
        sede = self.request.GET.get('sede')
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        ciudad = self.request.GET.get('ciudad')
        tipo_programa = self.request.GET.get('tipo_programa')

        if estado:
            queryset = queryset.filter(estado=estado)
        if profesor:
            queryset = queryset.filter(profesor_id=profesor)
        if materia:
            queryset = queryset.filter(materia_id=materia)
        if sede:
            queryset = queryset.filter(salon__sede_id=sede)
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        # Solo aplicar filtro de ciudad si es superuser
        if ciudad and self.request.user.is_superuser:
            queryset = queryset.filter(salon__sede__municipio__nombre=ciudad)
            
        # Filtrar por tipo de programa
        if tipo_programa:
            # Filtrar clases que tienen al menos un alumno con el tipo de programa seleccionado
            queryset = queryset.filter(grupo__alumnos_actuales__tipo_programa=tipo_programa).distinct()

        # Optimizar consultas y ordenar por fecha descendente
        return queryset.select_related(
            'profesor',
            'materia',
            'salon',
            'salon__sede',
            'grupo'
        ).order_by('-fecha', '-horario')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar el mensaje preformateado para cada clase
        for clase in context['clases']:
            profesor = clase.profesor
            
            # Renderizar el mensaje con los datos actuales
            # La fecha se formateará automáticamente en español gracias a la configuración de Django
            
            message_context = {
                'nombre': profesor.first_name,
                'fecha': clase.fecha,
                'materia': clase.materia.nombre,
                'sede': clase.salon.sede.nombre,
                'horario': clase.horario
            }
            
            # Renderizar el template y codificar para URL
            clase.whatsapp_message = render_to_string(
                'academico/mensaje_clase_profesor.txt',
                message_context
            ).replace('\n', '%0A').replace(' ', '%20')
        
        user = self.request.user
        # Lógica de contexto por rol
        if user.is_superuser:
            sedes = Sede.objects.all()
            context['ciudades'] = Municipio.objects.all()
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                sedes = Sede.objects.filter(municipio__departamento=user.departamento)
                context['ciudades'] = Municipio.objects.filter(departamento=user.departamento)
            else:
                sedes = Sede.objects.none()
                context['ciudades'] = Municipio.objects.none()
        else:
            # Otro personal (staff) ve solo su municipio
            sedes = Sede.objects.filter(municipio=user.municipio)
            context['ciudades'] = Municipio.objects.filter(id=user.municipio.id)
        
        context.update({
            'profesores': User.objects.filter(groups__name='Profesor'),
            'materias': Materia.objects.all(),
            'sedes': sedes,
            'estados_clase': Clase.ESTADO_CLASE,
            'tipos_programa': dict(Alumno.TIPO_PROGRAMA),
            'tipo_programa_seleccionado': self.request.GET.get('tipo_programa'),
            'titulo': 'Lista de Clases',
            'is_coordinador': user.groups.filter(name='CoordinadorDepartamental').exists()
        })
        return context
