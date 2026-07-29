from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlencode
from ..models import Alumno, Grupo
from ubicaciones.models import Municipio, Departamento, Sede

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

class AlumnosListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Alumno
    template_name = 'academico/alumnos_list.html'
    context_object_name = 'alumnos'
    paginate_by = 20
    login_url = 'login'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.es_docente and not user.is_superuser:
            return False
        return user.is_staff or getattr(user, 'is_observador', False) or user.es_personal_gestion
    
    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated and user.es_docente:
            return redirect('profesor_clases', profesor_id=user.id)
        return super().handle_no_permission()
        return redirect('login')

    def get_queryset(self):
        queryset = super().get_queryset().select_related('municipio__departamento', 'grupo_actual__salon__sede')
        user = self.request.user

        # Lógica de filtrado por rol
        if user.is_superuser:
            # Superusuario ve todo
            pass
        elif user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            # Coordinador o Auxiliar ven todo su departamento
            if hasattr(user, 'departamento') and user.departamento:
                queryset = queryset.filter(municipio__departamento=user.departamento)
        elif getattr(user, 'is_observador', False):
            # Observador de colegio ve solo su sede
            if hasattr(user, 'sede') and user.sede:
                queryset = queryset.filter(grupo_actual__salon__sede=user.sede)
            else:
                queryset = queryset.none()
        else:
            # Otro personal (staff) ve solo su municipio
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(municipio=user.municipio)
            else:
                queryset = queryset.none()

        # Aplicar filtros de búsqueda
        buscador = self.request.GET.get('buscador')
        sede = self.request.GET.get('sede')
        ciudad = self.request.GET.get('ciudad')
        departamento_id = self.request.GET.get('departamento')
        culminado = self.request.GET.get('culminado')
        estado_deuda = self.request.GET.get('estado_deuda')
        es_becado = self.request.GET.get('es_becado')
        tipo_programa = self.request.GET.get('tipo_programa')
        estado_alumno = self.request.GET.get('estado_alumno')  # Filtro de estado
        tiene_cuotas = self.request.GET.get('tiene_cuotas')    # Filtro de cuotas
        vendedor_id = self.request.GET.get('vendedor')
        grupo_id = self.request.GET.get('grupo')

        if buscador:
            from django.db.models import Q
            for term in buscador.split():
                regex_term = make_accent_insensitive_regex(term)
                queryset = queryset.filter(
                    Q(nombres__iregex=regex_term) |
                    Q(primer_apellido__iregex=regex_term) |
                    Q(segundo_apellido__iregex=regex_term) |
                    Q(identificacion__iregex=regex_term) |
                    Q(nombres_padre__iregex=regex_term) |
                    Q(nombres_madre__iregex=regex_term) |
                    Q(primer_apellido_padre__iregex=regex_term) |
                    Q(primer_apellido_madre__iregex=regex_term)
                )
        if sede:
            queryset = queryset.filter(grupo_actual__salon__sede__nombre__icontains=sede)
        # Filtros de ubicación jerárquicos para Superuser
        if self.request.user.is_superuser:
            if departamento_id:
                queryset = queryset.filter(municipio__departamento_id=departamento_id)
            if ciudad: # El filtro de ciudad puede refinar el de departamento
                queryset = queryset.filter(municipio__nombre__icontains=ciudad)
        # Filtro de ciudad para otros roles con permiso
        elif ciudad and self.request.user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            queryset = queryset.filter(municipio__nombre__icontains=ciudad)
            
        # Filtrar por estado de culminación
        fecha_actual = timezone.localtime(timezone.now()).date()
        if culminado == 'si':
            queryset = queryset.filter(fecha_culminacion__lt=fecha_actual)
        elif culminado == 'no':
            queryset = queryset.filter(fecha_culminacion__gte=fecha_actual)
            
        # Filtrar por estado de deuda
        if estado_deuda == 'pagada':
            queryset = queryset.filter(deuda__estado='pagada', deuda__saldo_pendiente=0)
        elif estado_deuda == 'pendiente':
            # Filtrar deudas con saldo pendiente mayor que 0, sin importar su estado formal
            queryset = queryset.filter(deuda__saldo_pendiente__gt=0)
        elif estado_deuda == 'no_tiene':
            queryset = queryset.filter(deuda__isnull=True)
            
        # Filtrar por beca
        if es_becado == 'si':
            queryset = queryset.filter(es_becado=True)
        elif es_becado == 'no':
            queryset = queryset.filter(es_becado=False)
            
        # Filtrar por tipo de programa
        if tipo_programa:
            queryset = queryset.filter(tipo_programa=tipo_programa)
            
        # Filtrar por estado del alumno (activo/retirado)
        if estado_alumno:
            queryset = queryset.filter(estado=estado_alumno)
            
        # Filtrar por si tiene cuotas asociadas
        if tiene_cuotas == 'si':
            queryset = queryset.filter(deuda__cuotas__isnull=False).distinct()
        elif tiene_cuotas == 'no':
            no_deuda = queryset.filter(deuda__isnull=True).distinct()
            deuda_sin_cuotas = queryset.filter(deuda__isnull=False, deuda__cuotas__isnull=True).distinct()
            queryset = no_deuda | deuda_sin_cuotas

        # Filtrar por vendedor
        if vendedor_id:
            queryset = queryset.filter(vendedor_id=vendedor_id)

        # Filtrar por grupo
        if grupo_id:
            queryset = queryset.filter(grupo_actual_id=grupo_id)

        # Filtrar por mes de culminación
        mes_culminacion = self.request.GET.get('mes_culminacion')
        if mes_culminacion:
            queryset = queryset.filter(fecha_culminacion__month=mes_culminacion)
            
        # Filtrar por año de culminación
        ano_culminacion = self.request.GET.get('ano_culminacion')
        if ano_culminacion:
            queryset = queryset.filter(fecha_culminacion__year=ano_culminacion)

        return queryset.order_by('primer_apellido')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros GET actuales
        get_params = self.request.GET.copy()
        
        # Eliminar 'page' si existe para evitar duplicados
        if 'page' in get_params:
            del get_params['page']
        
        # Convertir a string de consulta
        query_string = urlencode(get_params)
        
        # Agregar al contexto
        context['query_string'] = query_string
        
        # Importar modelos necesarios
        from academico.models import Alumno
        from ubicaciones.models import Departamento, Sede, Municipio
        from ventas.models import Vendedor
        
        # Añadir lista de sedes para los filtros
        context['sedes'] = Sede.objects.all()
        context['vendedores'] = Vendedor.objects.all()
        
        # Grupos disponibles según el rol del usuario y filtros activos
        grupos_qs = Grupo.objects.select_related('salon__sede__municipio__departamento').all()
        if not self.request.user.is_superuser:
            if self.request.user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
                if hasattr(self.request.user, 'departamento') and self.request.user.departamento:
                    grupos_qs = grupos_qs.filter(salon__sede__municipio__departamento=self.request.user.departamento)
            elif getattr(self.request.user, 'is_observador', False):
                if hasattr(self.request.user, 'sede') and self.request.user.sede:
                    grupos_qs = grupos_qs.filter(salon__sede=self.request.user.sede)
            else:
                if hasattr(self.request.user, 'municipio') and self.request.user.municipio:
                    grupos_qs = grupos_qs.filter(salon__sede__municipio=self.request.user.municipio)
        # Filtrar grupos según los filtros de ubicación seleccionados
        filtro_depto = self.request.GET.get('departamento')
        filtro_ciudad = self.request.GET.get('ciudad')
        filtro_sede = self.request.GET.get('sede')
        if filtro_sede:
            grupos_qs = grupos_qs.filter(salon__sede__nombre__icontains=filtro_sede)
        if filtro_depto:
            grupos_qs = grupos_qs.filter(salon__sede__municipio__departamento_id=filtro_depto)
        if filtro_ciudad:
            grupos_qs = grupos_qs.filter(salon__sede__municipio__nombre__icontains=filtro_ciudad)
        context['grupos'] = grupos_qs.order_by('codigo')
        context['grupo_seleccionado'] = self.request.GET.get('grupo', '')
        
        # Solo superusuarios tienen acceso a todos los departamentos
        if self.request.user.is_superuser:
            context['departamentos'] = Departamento.objects.all()
            context['ciudades'] = Municipio.objects.all()
        elif self.request.user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
            if hasattr(self.request.user, 'departamento') and self.request.user.departamento:
                context['ciudades'] = Municipio.objects.filter(departamento=self.request.user.departamento)
            else:
                context['ciudades'] = Municipio.objects.none()
        else:
            if hasattr(self.request.user, 'municipio') and self.request.user.municipio:
                context['ciudades'] = Municipio.objects.filter(id=self.request.user.municipio.id)
            else:
                context['ciudades'] = Municipio.objects.none()
                
        # Agregar tipos de programa y el valor seleccionado
        context['tipos_programa'] = dict(Alumno.TIPO_PROGRAMA)
        context['tipo_programa_seleccionado'] = self.request.GET.get('tipo_programa', '')
        context['departamento_seleccionado'] = self.request.GET.get('departamento', '')
        
        # Agregar meses y años de culminación
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
        context['mes_culminacion_seleccionado'] = self.request.GET.get('mes_culminacion', '')
        context['ano_culminacion_seleccionado'] = self.request.GET.get('ano_culminacion', '')
        
        # Determinar si el usuario es coordinador o auxiliar
        is_coordinador_or_auxiliar = self.request.user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists()
        context['is_coordinador_or_auxiliar'] = is_coordinador_or_auxiliar
        
        # Obtener el queryset filtrado y contar el total
        queryset = self.get_queryset()
        context['total_alumnos'] = queryset.count()
        
        # Generar paginación elidida (acortada)
        page_obj = context.get('page_obj')
        if page_obj:
            context['page_range'] = page_obj.paginator.get_elided_page_range(
                page_obj.number, on_each_side=2, on_ends=1
            )
        
        # Preparar alumnos con información adicional
        alumnos_con_info = []
        for alumno in context['page_obj']:
            # Determinar si el alumno ha culminado
            fecha_actual = timezone.localtime(timezone.now()).date()
            culminado = False
            if hasattr(alumno, 'fecha_culminacion') and alumno.fecha_culminacion and alumno.fecha_culminacion < fecha_actual:
                culminado = True
                
            # Determinar el estado de la deuda
            estado_deuda = 'no_tiene'
            if hasattr(alumno, 'deuda') and alumno.deuda:
                # Si tiene deuda con saldo pendiente > 0, debe mostrarse como 'pendiente' sin importar el estado
                if alumno.deuda.saldo_pendiente > 0:
                    estado_deuda = 'pendiente'
                else:
                    estado_deuda = alumno.deuda.estado
            
            # Añadir información al alumno
            alumno.culminado = culminado
            alumno.estado_deuda = estado_deuda
            
            # Verificar si tiene cuotas asociadas
            try:
                tiene_cuotas = alumno.deuda and alumno.deuda.cuotas.exists()
            except Exception as e:
                tiene_cuotas = False
                
            alumno.tiene_cuotas = tiene_cuotas
            # Ya tenemos acceso directo a es_becado desde el modelo
            alumnos_con_info.append(alumno)
            
        context['alumnos'] = alumnos_con_info
        
        # Preparar mensaje para mostrar los filtros activos
        filtros_activos = []
        if self.request.GET.get('buscador'):
            filtros_activos.append(f"Búsqueda: {self.request.GET.get('buscador')}")
        if self.request.GET.get('sede'):
            filtros_activos.append(f"Sede: {self.request.GET.get('sede')}")
        if self.request.GET.get('departamento'):
            try:
                depto = Departamento.objects.get(id=self.request.GET.get('departamento'))
                filtros_activos.append(f"Departamento: {depto.nombre}")
            except Exception:
                pass
        if self.request.GET.get('ciudad'):
            filtros_activos.append(f"Ciudad: {self.request.GET.get('ciudad')}")
        if self.request.GET.get('culminado') == 'si':
            filtros_activos.append("Culminado: Sí")
        elif self.request.GET.get('culminado') == 'no':
            filtros_activos.append("Culminado: No")
        if self.request.GET.get('estado_deuda') == 'pagada':
            filtros_activos.append("Estado Deuda: Pagada")
        elif self.request.GET.get('estado_deuda') == 'pendiente':
            filtros_activos.append("Estado Deuda: Pendiente")
        elif self.request.GET.get('estado_deuda') == 'no_tiene':
            filtros_activos.append("Estado Deuda: No tiene")
        if self.request.GET.get('es_becado') == 'si':
            filtros_activos.append("Becado: Sí")
        elif self.request.GET.get('es_becado') == 'no':
            filtros_activos.append("Becado: No")
        if self.request.GET.get('tipo_programa'):
            programas = dict(Alumno.TIPO_PROGRAMA)
            tipo_programa = self.request.GET.get('tipo_programa')
            filtros_activos.append(f"Programa: {programas.get(tipo_programa, tipo_programa)}")
        if self.request.GET.get('estado_alumno') == 'activo':
            filtros_activos.append("Estado: Activo")
        elif self.request.GET.get('estado_alumno') == 'retirado':
            filtros_activos.append("Estado: Retirado")
        if self.request.GET.get('tiene_cuotas') == 'si':
            filtros_activos.append("Tiene Cuotas: Sí")
        elif self.request.GET.get('tiene_cuotas') == 'no':
            filtros_activos.append("Tiene Cuotas: No")
            
        if self.request.GET.get('mes_culminacion'):
            meses_dict = dict(context['meses_anio'])
            mes_nombre = meses_dict.get(self.request.GET.get('mes_culminacion'))
            filtros_activos.append(f"Mes Culminación: {mes_nombre}")
        if self.request.GET.get('ano_culminacion'):
            filtros_activos.append(f"Año Culminación: {self.request.GET.get('ano_culminacion')}")

        if self.request.GET.get('vendedor'):
            try:
                vend = Vendedor.objects.get(id=self.request.GET.get('vendedor'))
                filtros_activos.append(f"Vendedor: {vend.nombres} {vend.apellidos}")
            except Exception:
                pass
        if self.request.GET.get('grupo'):
            try:
                grp = Grupo.objects.get(id=self.request.GET.get('grupo'))
                filtros_activos.append(f"Grupo: {grp.codigo}")
            except Exception:
                pass
            
        context['filtros_activos'] = filtros_activos
        
        return context