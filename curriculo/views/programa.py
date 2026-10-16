from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Prefetch
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django import forms

from curriculo.models import Programa, Ciclo, Modulo
from curriculo.models.core import ClaseVirtual, Asistencia
from curriculo.views.mixins import HistorialMixin, ProgramaVisibilidadMixin


# ── Forms ─────────────────────────────────────────────────────────────────────

class CicloForm(forms.ModelForm):
    class Meta:
        model = Ciclo
        fields = ['nombre', 'orden', 'visible']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'visible': forms.CheckboxInput(attrs={'class': 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
        }


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ['nombre', 'descripcion', 'orden', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'descripcion': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'activo': forms.CheckboxInput(attrs={'class': 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
        }


# ── Hub & Dashboard ───────────────────────────────────────────────────────────

class ProgramaHubView(LoginRequiredMixin, ListView):
    """
    Página de inicio/hub del área académica.
    Redirige automáticamente si el usuario solo tiene 1 programa activo.
    """
    model = Programa
    template_name = 'curriculo/programa_hub.html'
    context_object_name = 'programas_inscritos'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Programa.objects.filter(activo=True)
        if user.es_docente:
            return user.programas_docente.filter(activo=True)
            
        # Para estudiantes, verificar suscripción activa
        from suscripciones.models import Subscription
        from django.utils import timezone
        hoy = timezone.now().date()
        suscripcion_activa = user.subscriptions.filter(active=True, end_date__gte=hoy).exists()
        if suscripcion_activa and user.programa_id and user.programa.activo:
            return Programa.objects.filter(id=user.programa_id)
        return Programa.objects.none()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        qs = self.get_queryset()
        if qs.count() == 1:
            return redirect('curriculo:programa_dashboard', slug=qs.first().slug)
        elif qs.count() == 0 and not request.user.is_superuser and not request.user.es_docente and not request.user.es_personal_gestion:
            messages.info(request, "Aún no tienes programas inscritos activos.")
            return redirect('suscripciones:mi_suscripcion')
            
        return super().dispatch(request, *args, **kwargs)



def obtener_estadisticas_estudiante(user, programa):
    """
    Calcula las estadisticas reales de progreso y desempeno para estudiantes
    tanto presenciales como virtuales. Retorna None si no hay informacion para procesar
    o si el usuario es personal docente/administrativo.
    """
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    if user.es_personal_gestion:
        return None
    if user.es_docente and not getattr(user, 'es_estudiante_virtual', False) and not getattr(user, 'perfil_alumno', None):
        return None

    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Q
    from academico.models import Alumno, Asistencia as AsistenciaPresencial, Clase as ClasePresencial
    from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
    from evaluaciones.models.simulacros import Simulacro as SimulacroVirtual, IntentoSimulacro, RespuestaSimulacro
    from evaluaciones.models.talleres import Taller, IntentoTaller, RespuestaTaller

    alumno = getattr(user, 'perfil_alumno', None)
    if not alumno:
        alumno = Alumno.objects.filter(usuario=user).first()
    if not alumno and user.numero_documento:
        alumno = Alumno.objects.filter(identificacion__iexact=user.numero_documento).first()

    # 1. Clases completadas (asistidas)
    asist_virt = Asistencia.objects.filter(
        alumno=user,
        asistio=True,
        clase__modulo__ciclo__programa=programa
    ).count()
    asist_pres = 0
    if alumno:
        asist_pres = AsistenciaPresencial.objects.filter(alumno=alumno, asistio=True).count()
    total_clases = asist_virt + asist_pres

    # 2. Simulacros hechos
    sim_virt = IntentoSimulacro.objects.filter(
        usuario=user,
        fecha_fin__isnull=False
    ).count()
    sim_pres = 0
    diag_pres = 0
    if alumno:
        sim_pres = ResultadoSimulacro.objects.filter(alumno=alumno).count()
        diag_pres = ResultadoSimulacroDiagnostico.objects.filter(alumno=alumno).count()
    total_simulacros = sim_virt + sim_pres + diag_pres

    # 3. Preguntas respondidas
    resp_talleres = RespuestaTaller.objects.filter(intento__usuario=user).count()
    resp_sim_virt = RespuestaSimulacro.objects.filter(intento_sesion__intento_simulacro__usuario=user).count()
    resp_sim_pres = 0
    if alumno:
        for r in ResultadoSimulacro.objects.filter(alumno=alumno):
            resp_sim_pres += len(r.respuestas_s1 or '') + len(r.respuestas_s2 or '')
        for r in ResultadoSimulacroDiagnostico.objects.filter(alumno=alumno):
            resp_sim_pres += len(r.respuestas_s1 or '') + len(r.respuestas_s2 or '')
    total_preguntas = resp_talleres + resp_sim_virt + resp_sim_pres

    # 4. Historial de puntajes de simulacros para estimacion y diferencia
    scores = []
    if alumno:
        for r in ResultadoSimulacro.objects.filter(alumno=alumno).order_by('fecha_realizacion', 'id'):
            pt = r.puntaje_global_mostrado
            if pt and pt > 0:
                scores.append((r.fecha_realizacion, round(pt)))
        for r in ResultadoSimulacroDiagnostico.objects.filter(alumno=alumno).order_by('fecha_realizacion', 'id'):
            pt = r.puntaje_global_mostrado
            if pt and pt > 0:
                scores.append((r.fecha_realizacion, round(pt)))
    for isim in IntentoSimulacro.objects.filter(usuario=user, fecha_fin__isnull=False).order_by('fecha_fin', 'id'):
        pt = isim.puntaje_global
        if pt and pt > 0:
            scores.append((timezone.localtime(isim.fecha_fin).date(), round(pt)))

    scores.sort(key=lambda x: (x[0] is not None, x[0]))

    puntaje_estimado = None
    diff_texto = None
    diff_tipo = None

    if scores:
        puntaje_estimado = scores[-1][1]
        if len(scores) >= 2:
            diff = scores[-1][1] - scores[-2][1]
            if diff > 0:
                diff_texto = f"+{diff} pts"
                diff_tipo = 'positivo'
            elif diff < 0:
                diff_texto = f"{diff} pts"
                diff_tipo = 'negativo'
            else:
                diff_texto = "0 pts"
                diff_tipo = 'neutro'
    else:
        # Si no tiene simulacros, estimar con el promedio de talleres
        talleres_scores = list(IntentoTaller.objects.filter(
            usuario=user,
            puntaje_porcentaje__isnull=False
        ).values_list('puntaje_porcentaje', flat=True))
        if talleres_scores:
            avg_pct = sum(talleres_scores) / len(talleres_scores)
            puntaje_estimado = round((avg_pct / 100) * 500)

    # Si no tiene informacion para procesar, no mostrar nada
    if total_clases == 0 and total_simulacros == 0 and total_preguntas == 0 and puntaje_estimado is None:
        return None

    # 5. Dias en racha
    active_dates = set()
    if alumno:
        for a in AsistenciaPresencial.objects.filter(alumno=alumno, asistio=True).select_related('clase'):
            if a.clase and a.clase.fecha:
                active_dates.add(a.clase.fecha)
        for r in ResultadoSimulacro.objects.filter(alumno=alumno):
            if r.fecha_realizacion:
                active_dates.add(r.fecha_realizacion)
    for av in Asistencia.objects.filter(alumno=user, asistio=True).select_related('clase'):
        if av.clase and av.clase.fecha:
            active_dates.add(av.clase.fecha)
    for it in IntentoTaller.objects.filter(usuario=user):
        d = it.fecha_fin or it.fecha_inicio
        if d:
            active_dates.add(timezone.localtime(d).date())
    for isim in IntentoSimulacro.objects.filter(usuario=user):
        d = isim.fecha_fin or isim.fecha_inicio
        if d:
            active_dates.add(timezone.localtime(d).date())

    hoy = timezone.localtime(timezone.now()).date()
    if active_dates:
        active_dates.add(hoy)

    racha = 0
    curr = hoy
    while curr in active_dates:
        racha += 1
        curr -= timedelta(days=1)

    # 6. Total completados y porcentaje
    tot_clases_virt = ClaseVirtual.objects.filter(modulo__ciclo__programa=programa).count()
    tot_clases_pres = 0
    if alumno and alumno.grupo_actual:
        tot_clases_pres = ClasePresencial.objects.filter(grupo=alumno.grupo_actual, estado='vista').count()
    tot_talleres = Taller.objects.filter(modulo__ciclo__programa=programa, estado='publicado').count()
    tot_sim = SimulacroVirtual.objects.filter(Q(modulo__isnull=True) | Q(modulo__ciclo__programa=programa), estado='publicado').count()
    if alumno:
        tot_sim += ResultadoSimulacro.objects.filter(alumno=alumno).values('simulacro_id').distinct().count()

    total_disponibles = tot_clases_virt + tot_clases_pres + tot_talleres + tot_sim
    talleres_hechos = IntentoTaller.objects.filter(usuario=user, fecha_fin__isnull=False).values('taller_id').distinct().count()
    total_completados = total_clases + talleres_hechos + total_simulacros

    if total_disponibles > 0 and total_completados > 0:
        pct_completado = min(100, round((total_completados / total_disponibles) * 100))
    else:
        pct_completado = 0

    stroke_dashoffset = round(251.2 * (1 - (pct_completado / 100.0)), 2)
    meta_personal = getattr(user, 'meta_puntaje', None) or 380
    pct_meta = min(100, round((puntaje_estimado / meta_personal * 100))) if puntaje_estimado else 0
    total_preguntas_formateado = f"{total_preguntas:,}".replace(",", ".")

    return {
        'total_clases': total_clases,
        'total_simulacros': total_simulacros,
        'total_preguntas': total_preguntas,
        'total_preguntas_formateado': total_preguntas_formateado,
        'racha': racha,
        'pct_completado': pct_completado,
        'stroke_dashoffset': stroke_dashoffset,
        'puntaje_estimado': puntaje_estimado,
        'diff_texto': diff_texto,
        'diff_tipo': diff_tipo,
        'meta_personal': meta_personal,
        'pct_meta': pct_meta,
    }


def calcular_progreso_areas(user, alumno=None):
    """
    Calcula el progreso/rendimiento por área (0-100%) para el estudiante.
    Retorna None si no hay información evaluada o si el usuario es staff/docente.
    """
    if not user.is_authenticated or user.is_superuser or user.es_personal_gestion:
        return None

    from academico.models import Alumno, Nota
    from simulacros.models import ResultadoSimulacro, ResultadoSimulacroDiagnostico
    from evaluaciones.models.talleres import IntentoTaller
    from evaluaciones.models.simulacros import IntentoSimulacro

    if not alumno:
        alumno = getattr(user, 'perfil_alumno', None)
        if not alumno:
            alumno = Alumno.objects.filter(usuario=user).first()
        if not alumno and user.numero_documento:
            alumno = Alumno.objects.filter(identificacion__iexact=user.numero_documento).first()

    if user.es_docente and not getattr(user, 'es_estudiante_virtual', False) and not alumno:
        return None

    areas_config = {
        'Lectura Crítica': {
            'keywords': ['lectura', 'español', 'lenguaje'],
            'color': 'bg-purple-600',
            'dot_color': 'bg-purple-600',
            'valores': []
        },
        'Matemáticas': {
            'keywords': ['matemática', 'razonamiento', 'estadística', 'matematica'],
            'color': 'bg-blue-600',
            'dot_color': 'bg-blue-600',
            'valores': []
        },
        'Ciencias Naturales': {
            'keywords': ['física', 'fisica', 'química', 'quimica', 'biología', 'biologia', 'natural'],
            'color': 'bg-teal-600',
            'dot_color': 'bg-teal-600',
            'valores': []
        },
        'Sociales y Ciudadanas': {
            'keywords': ['social', 'ciudadana', 'filosofía', 'filosofia'],
            'color': 'bg-rose-500',
            'dot_color': 'bg-rose-500',
            'valores': []
        },
        'Inglés': {
            'keywords': ['inglés', 'ingles', 'english'],
            'color': 'bg-amber-500',
            'dot_color': 'bg-amber-500',
            'valores': []
        },
    }

    def agregar_valor(nombre_materia, pct):
        if pct is None:
            return
        nombre_lower = (nombre_materia or '').lower()
        for area_nombre, cfg in areas_config.items():
            if any(kw in nombre_lower for kw in cfg['keywords']):
                try:
                    cfg['valores'].append(float(pct))
                except (ValueError, TypeError):
                    pass
                return

    # 1. Intentos de talleres virtuales (puntaje_porcentaje 0-100)
    for it in IntentoTaller.objects.filter(usuario=user, fecha_fin__isnull=False, puntaje_porcentaje__isnull=False).select_related('taller__tema__materia'):
        materia_nombre = ''
        if it.taller and it.taller.tema and it.taller.tema.materia:
            materia_nombre = it.taller.tema.materia.nombre
        agregar_valor(materia_nombre, it.puntaje_porcentaje)

    # 2. Simulacros virtuales
    for isim in IntentoSimulacro.objects.filter(usuario=user, fecha_fin__isnull=False):
        if isim.resultados_detallados and isinstance(isim.resultados_detallados, list):
            for comp in isim.resultados_detallados:
                mat_nom = comp.get('materia_nombre', '')
                pct = comp.get('porcentaje')
                agregar_valor(mat_nom, pct)

    # 3. Presencial: Notas de clase (escala 0.0 - 5.0 -> a porcentaje 0-100)
    if alumno:
        for n in Nota.objects.filter(alumno=alumno, clase__estado='vista').select_related('clase__materia'):
            if n.clase and n.clase.materia and n.nota is not None:
                try:
                    pct = (float(n.nota) / 5.0) * 100
                    agregar_valor(n.clase.materia.nombre, pct)
                except (ValueError, TypeError):
                    pass

        # 4. Presencial: Resultados de simulacros
        for r in ResultadoSimulacro.objects.filter(alumno=alumno):
            agregar_valor('Lectura Crítica', r.puntaje_lectura)
            agregar_valor('Matemáticas', r.puntaje_matematicas)
            agregar_valor('Ciencias Naturales', r.puntaje_naturales)
            agregar_valor('Sociales y Ciudadanas', r.puntaje_sociales)
            agregar_valor('Inglés', r.puntaje_ingles)

        for rd in ResultadoSimulacroDiagnostico.objects.filter(alumno=alumno):
            agregar_valor('Lectura Crítica', rd.puntaje_lectura)
            agregar_valor('Matemáticas', rd.puntaje_matematicas)
            agregar_valor('Ciencias Naturales', rd.puntaje_naturales)
            agregar_valor('Sociales y Ciudadanas', rd.puntaje_sociales)
            agregar_valor('Inglés', rd.puntaje_ingles)

    resultado = []
    tiene_datos_area = False
    for area_nombre, cfg in areas_config.items():
        if cfg['valores']:
            promedio = round(sum(cfg['valores']) / len(cfg['valores']))
            promedio = min(100, max(0, promedio))
            tiene_datos_area = True
        else:
            promedio = None
        resultado.append({
            'nombre': area_nombre,
            'porcentaje': promedio if promedio is not None else 0,
            'porcentaje_display': f'{promedio}%' if promedio is not None else 'Sin evaluar',
            'tiene_datos': promedio is not None,
            'color': cfg['color'],
            'dot_color': cfg['dot_color'],
        })

    return resultado if tiene_datos_area else None

class ProgramaDashboardView(LoginRequiredMixin, ProgramaVisibilidadMixin, DetailView):
    """
    Muestra los ciclos, módulos y recursos específicos de un Programa.
    """
    model = Programa
    template_name = 'curriculo/programa_dashboard.html'
    context_object_name = 'programa'
    slug_url_kwarg = 'slug'

    def _resolver_programa(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programa = self.object
        user = self.request.user

        # Calcular si el usuario actual es profesor o administrador de este programa específico
        es_teacher = user.is_superuser or (
            user.es_docente and user.programas_docente.filter(id=programa.id).exists()
        )
        context['es_teacher'] = es_teacher

        # Filtrar los ciclos visibles para estudiantes
        if es_teacher or user.is_staff or user.is_superuser:
            ciclos_qs = programa.ciclos.all().order_by('orden')
        else:
            ciclos_qs = programa.ciclos.filter(visible=True).order_by('orden')

        # Prefetching de recursos
        from evaluaciones.models.talleres import Taller
        if es_teacher or user.is_staff or user.is_superuser:
            talleres_qs = Taller.objects.all().order_by('orden')
        else:
            talleres_qs = Taller.objects.filter(estado='publicado').order_by('orden')

        clases_qs = ClaseVirtual.objects.all()

        if es_teacher or user.is_staff or user.is_superuser:
            modulos_qs = Modulo.objects.all()
        else:
            modulos_qs = Modulo.objects.filter(activo=True)

        modulos_qs = modulos_qs.prefetch_related(
            'posts',
            Prefetch('talleres', queryset=talleres_qs),
            'simulacros',
            Prefetch('clases_virtuales', queryset=clases_qs)
        ).order_by('orden')

        context['ciclos'] = ciclos_qs.prefetch_related(
            Prefetch('modulos', queryset=modulos_qs)
        )

        # Asistencias
        if user.is_authenticated and not user.is_staff:
            mis_asistencias = Asistencia.objects.filter(
                alumno=user,
                clase__modulo__ciclo__programa=programa
            ).values('clase_id', 'asistio')
            context['clases_registradas'] = {a['clase_id'] for a in mis_asistencias}
            context['clases_asistidas'] = {a['clase_id'] for a in mis_asistencias if a['asistio']}
        else:
            context['clases_registradas'] = set()
            context['clases_asistidas'] = set()

        # Estadisticas rapidas reales del estudiante (presencial o virtual)
        context['stats_estudiante'] = obtener_estadisticas_estudiante(user, programa)
        context['progreso_areas'] = calcular_progreso_areas(user)

        return context


# ── Ciclo CRUD ────────────────────────────────────────────────────────────────

class CicloCreateView(LoginRequiredMixin, HistorialMixin, CreateView):
    model = Ciclo
    form_class = CicloForm
    template_name = 'curriculo/ciclo_form.html'

    def form_valid(self, form):
        programa = get_object_or_404(Programa, slug=self.kwargs.get('slug'))
        form.instance.programa = programa
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.kwargs.get('slug')})


class CicloUpdateView(LoginRequiredMixin, HistorialMixin, UpdateView):
    model = Ciclo
    form_class = CicloForm
    template_name = 'curriculo/ciclo_form.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.programa.slug})


class CicloDeleteView(LoginRequiredMixin, HistorialMixin, DeleteView):
    model = Ciclo
    template_name = 'curriculo/ciclo_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.programa.slug})


# ── Módulo CRUD ───────────────────────────────────────────────────────────────

class ModuloCreateView(LoginRequiredMixin, HistorialMixin, CreateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'

    def form_valid(self, form):
        ciclo = get_object_or_404(Ciclo, id=self.kwargs.get('ciclo_id'))
        form.instance.ciclo = ciclo
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.ciclo.programa.slug})


class ModuloUpdateView(LoginRequiredMixin, HistorialMixin, UpdateView):
    model = Modulo
    form_class = ModuloForm
    template_name = 'curriculo/modulo_form.html'

    def get_success_url(self):
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': self.object.ciclo.programa.slug})


class ModuloDeleteView(LoginRequiredMixin, HistorialMixin, DeleteView):
    model = Modulo
    template_name = 'curriculo/modulo_confirm_delete.html'

    def get_success_url(self):
        slug = self.object.ciclo.programa.slug
        return reverse_lazy('curriculo:programa_dashboard', kwargs={'slug': slug})


# ── Asistencia ────────────────────────────────────────────────────────────────

class RegistrarAsistenciaView(LoginRequiredMixin, View):
    def post(self, request, clase_id):
        clase = get_object_or_404(ClaseVirtual, id=clase_id)
        programa = clase.modulo.ciclo.programa
        
        if not clase.is_active_for_attendance():
            messages.error(request, f"No puedes registrar asistencia para '{clase.titulo}' en este momento. La clase no está en curso.")
            return redirect('curriculo:programa_dashboard', slug=programa.slug)
        
        asistencia, created = Asistencia.objects.get_or_create(
            clase=clase,
            alumno=request.user,
            defaults={'asistio': True}
        )
        
        if not created:
            if asistencia.asistio:
                messages.info(request, "Ya habías registrado tu asistencia previamente.")
            else:
                asistencia.asistio = True
                asistencia.save()
                messages.success(request, f"¡Asistencia registrada exitosamente para {clase.titulo}!")
        else:
            messages.success(request, f"¡Asistencia registrada exitosamente para {clase.titulo}!")
            
        return redirect('curriculo:programa_dashboard', slug=programa.slug)


# ── Meta Puntaje Personal ────────────────────────────────────────────────────

class ActualizarMetaPuntajeView(LoginRequiredMixin, View):
    """
    Permite al estudiante actualizar su puntaje meta personal (100 - 500).
    """
    def post(self, request):
        meta = request.POST.get('meta_puntaje')
        if meta:
            try:
                meta_val = int(meta)
                if 100 <= meta_val <= 500:
                    request.user.meta_puntaje = meta_val
                    request.user.save(update_fields=['meta_puntaje'])
                    messages.success(request, f"¡Meta personal actualizada a {meta_val} puntos!")
                else:
                    messages.error(request, "La meta debe estar entre 100 y 500 puntos.")
            except (ValueError, TypeError):
                messages.error(request, "El puntaje ingresado no es válido.")

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
        if next_url:
            return redirect(next_url)
        return redirect('curriculo:programa_list')
