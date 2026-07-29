from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from datetime import datetime, timedelta

from academico.models import Clase, Alumno
from ubicaciones.models import Sede, Municipio

class CronogramaView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'academico/cronograma.html'
    
    def test_func(self):
        # Verificar si el usuario es superuser o pertenece a los grupos permitidos
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros de filtro
        fecha_str = self.request.GET.get('fecha')
        sede_id = self.request.GET.get('sede')
        tipo_horario = self.request.GET.get('tipo')  # AM o PM
        municipio_id = self.request.GET.get('municipio')
        tipo_programa = self.request.GET.get('tipo_programa')
        
        # Convertir 'None' en None para evitar errores de tipo
        if sede_id == 'None':
            sede_id = None
        if municipio_id == 'None':
            municipio_id = None
        if tipo_horario == 'None':
            tipo_horario = None
        if tipo_programa == 'None':
            tipo_programa = None
        
        # Establecer fecha inicial si no se proporciona
        if fecha_str:
            fecha_inicial = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha_inicial = datetime.now().date()
            # Ajustar a lunes si no lo es
            while fecha_inicial.weekday() != 0:
                fecha_inicial -= timedelta(days=1)
        
        # Calcular rango de fechas (lunes a sábado)
        fechas = []
        for i in range(6):  # 0 = lunes, 5 = sábado
            fecha = fecha_inicial + timedelta(days=i)
            fechas.append(fecha)
        
        user = self.request.user
        # Filtrar sedes y municipios según el rol del usuario
        if user.is_superuser:
            sedes = Sede.objects.all()
            municipios = Municipio.objects.all()
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if user.departamento:
                sedes = Sede.objects.filter(municipio__departamento=user.departamento)
                municipios = Municipio.objects.filter(departamento=user.departamento)
            else:
                sedes = Sede.objects.none()
                municipios = Municipio.objects.none()
        else:
            sedes = Sede.objects.filter(municipio=user.municipio)
            municipios = Municipio.objects.filter(id=user.municipio.id)

        # Aplicar filtros a las clases
        clases = Clase.objects.filter(fecha__range=[fecha_inicial, fechas[-1]])

        # Filtrado inicial por rol
        if not user.is_superuser:
            if user.groups.filter(name='CoordinadorDepartamental').exists():
                if user.departamento:
                    clases = clases.filter(salon__sede__municipio__departamento=user.departamento)
            else:
                clases = clases.filter(salon__sede__municipio=user.municipio)

        if sede_id and sede_id != 'None':
            clases = clases.filter(salon__sede_id=sede_id)
        
        if municipio_id and municipio_id != 'None' and self.request.user.is_superuser:
            clases = clases.filter(salon__sede__municipio_id=municipio_id)
        
        if tipo_horario:
            if tipo_horario == 'AM':
                clases = clases.filter(
                    Q(horario__startswith='08:00') |
                    Q(horario__startswith='10:00') |
                    Q(horario__startswith='7:00')
                )
            elif tipo_horario == 'PM':
                clases = clases.filter(horario__startswith='15:00')
                
        # Filtrar por tipo de programa
        if tipo_programa:
            # Filtrar clases que tienen al menos un alumno con el tipo de programa seleccionado
            clases = clases.filter(grupo__alumnos_actuales__tipo_programa=tipo_programa).distinct()
        
        # Organizar clases por salón y fecha
        clases_organizadas = {}
        for clase in clases:
            salon_key = clase.salon.id
            if salon_key not in clases_organizadas:
                clases_organizadas[salon_key] = {
                    'salon': clase.salon,
                    'clases': {fecha: [] for fecha in fechas}
                }
            clases_organizadas[salon_key]['clases'][clase.fecha].append(clase)
        
        context.update({
            'fechas': fechas,
            'clases_organizadas': clases_organizadas,
            'sedes': sedes,
            'municipios': municipios,
            'fecha_actual': fecha_inicial,
            'fecha_anterior': fecha_inicial - timedelta(days=7),
            'fecha_siguiente': fecha_inicial + timedelta(days=7),
            'sede_seleccionada': sede_id,
            'municipio_seleccionado': municipio_id,
            'tipo_horario': tipo_horario,
            'tipo_programa_seleccionado': tipo_programa,
            'tipos_programa': dict(Alumno.TIPO_PROGRAMA),
            'puede_editar': self.request.user.is_superuser or 
                          self.request.user.groups.filter(name='SecretariaAcademica').exists()
        })
        
        return context
