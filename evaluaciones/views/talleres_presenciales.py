from django.views.generic import ListView, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime

from academico.models.clase import Clase
from academico.models.alumno import Alumno
from academico.models.asistencia import Asistencia
from academico.models.nota import Nota
from evaluaciones.models.talleres import Taller, IntentoTaller, RespuestaTaller
from evaluaciones.models.banco import Opcion
from evaluaciones.views.talleres import agrupar_por_bloque
from usuarios.models import User


def get_alumno_for_user(user):
    """
    Resuelve el registro de Alumno para un User por:
    1. FK directa user.perfil_alumno
    2. Alumno.identificacion == user.username
    3. Coincidencia por Nombres y Apellidos (user.first_name + user.last_name)
    Vincula automáticamente el usuario al Alumno en base de datos.
    """
    if not user or not user.is_authenticated:
        return None
        
    alumno = getattr(user, 'perfil_alumno', None)
    if alumno:
        return alumno
        
    username_clean = str(user.username).strip()
    alumno = Alumno.objects.filter(identificacion=username_clean).first()
    if not alumno:
        alumno = Alumno.objects.filter(identificacion__iexact=username_clean).first()
        
    if not alumno and user.first_name and user.last_name:
        fname = user.first_name.strip()
        lname_parts = user.last_name.strip().split()
        p_apellido = lname_parts[0] if lname_parts else ''
        s_apellido = lname_parts[1] if len(lname_parts) > 1 else ''
        
        qs = Alumno.objects.filter(nombres__iexact=fname, primer_apellido__iexact=p_apellido)
        if s_apellido:
            qs_exact = qs.filter(segundo_apellido__iexact=s_apellido)
            if qs_exact.exists():
                qs = qs_exact
        alumno = qs.first()

    if alumno and not alumno.usuario:
        try:
            alumno.usuario = user
            alumno.save(update_fields=['usuario'])
        except Exception:
            pass
            
    return alumno


class MisClasesPresencialesView(LoginRequiredMixin, ListView):
    """
    Muestra al estudiante sus clases presenciales del día de hoy (o recientes)
    y el estado de asistencia y talleres asignados a cada clase.
    """
    model = Clase
    template_name = 'academico/mis_clases_presenciales.html'
    context_object_name = 'clases_hoy'

    def get_queryset(self):
        user = self.request.user
        alumno = get_alumno_for_user(user)
            
        if not alumno or not alumno.grupo_actual:
            return Clase.objects.none()

        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            try:
                fecha_filtro = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                return Clase.objects.filter(
                    grupo=alumno.grupo_actual,
                    fecha=fecha_filtro
                ).select_related('materia', 'salon', 'profesor', 'taller').order_by('horario')
            except ValueError:
                pass

        hoy = timezone.now().date()
        return Clase.objects.filter(
            grupo=alumno.grupo_actual,
            fecha__gte=hoy - timedelta(days=2)
        ).select_related('materia', 'salon', 'profesor', 'taller').order_by('-fecha', 'horario')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        alumno = get_alumno_for_user(user)

        clases_info = []
        ahora = timezone.now()

        for clase in context['clases_hoy']:
            asistencia = None
            if alumno:
                asistencia = Asistencia.objects.filter(alumno=alumno, clase=clase).first()

            asistio = bool(asistencia and asistencia.asistio)
            fin_clase = clase.get_datetime_fin()
            tiempo_expirado = ahora > (fin_clase + timedelta(minutes=5))

            intento_existente = None
            if clase.taller:
                intento_existente = IntentoTaller.objects.filter(usuario=user, taller=clase.taller, clase=clase).first()
                if not intento_existente:
                    intento_existente = IntentoTaller.objects.filter(usuario=user, taller=clase.taller).first()

            clases_info.append({
                'clase': clase,
                'asistio': asistio,
                'tiempo_expirado': tiempo_expirado,
                'intento': intento_existente,
                'puede_resolver': (clase.taller is not None and asistio and (not intento_existente or not intento_existente.fecha_fin) and not clase.taller_cerrado)
            })

        context['clases_info'] = clases_info
        context['titulo'] = 'Mis Clases Presenciales del Día'
        return context


class TallerPresencialEjecutarView(LoginRequiredMixin, TemplateView):
    """
    Vista de resolución presencial de un Taller asignado a una Clase presencial:
    - Requiere asistencia confirmada (asistio=True) por el docente.
    - Si la recepción está abierta, permite marcar respuestas.
    - Una vez entregado o cerrado el taller por el docente, entra en Modo Lectura y Socialización.
    - Liberadas las notas por el profesor, redirige al solucionario completo.
    """
    template_name = 'evaluaciones/taller_presencial_resolver.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        user = request.user

        # Superusuarios o el profesor asignado pueden ver en vista previa sin restricciones
        if user.is_superuser or user == clase.profesor:
            return super().dispatch(request, *args, **kwargs)

        # 1. Verificar registro de alumno
        alumno = get_alumno_for_user(user)

        # 2. Verificar asistencia confirmada por el profesor
        asistencia = None
        if alumno:
            asistencia = Asistencia.objects.filter(alumno=alumno, clase=clase).first()

        if not asistencia or not asistencia.asistio:
            messages.error(
                request,
                "Acceso Restringido: Tu profesor aún no ha verificado o confirmado tu asistencia (Presente) a esta clase presencial."
            )
            return redirect('mis_clases_presenciales')

        # 3. Verificar que la clase posea un taller
        if not clase.taller:
            messages.error(request, "Esta clase presencial no tiene un taller interactivo asignado.")
            return redirect('mis_clases_presenciales')

        # 4. Si el taller presencial ya tiene notas liberadas por el docente y el estudiante completó su intento
        intento_completado = IntentoTaller.objects.filter(usuario=user, taller=clase.taller, clase=clase, fecha_fin__isnull=False).first()
        if not intento_completado:
            intento_completado = IntentoTaller.objects.filter(usuario=user, taller=clase.taller, fecha_fin__isnull=False).first()

        if intento_completado and clase.taller_notas_liberadas:
            return redirect('evaluaciones:taller_intento_detail', pk=intento_completado.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        taller = clase.taller

        preguntas_taller = taller.preguntas_taller.select_related('pregunta').all()
        modo_vista_previa = self.request.user.is_superuser or self.request.user == clase.profesor
        
        intento = None
        if not modo_vista_previa:
            intento = IntentoTaller.objects.filter(usuario=self.request.user, taller=taller, clase=clase).first()
            if not intento:
                intento = IntentoTaller.objects.filter(usuario=self.request.user, taller=taller).first()
            if not intento:
                intento = IntentoTaller.objects.create(
                    usuario=self.request.user,
                    taller=taller,
                    clase=clase,
                    puntaje_porcentaje=0
                )
            elif not intento.clase:
                intento.clase = clase
                intento.save(update_fields=['clase'])

        entregado = bool(intento and intento.fecha_fin)
        modo_lectura_socializacion = (entregado or clase.taller_cerrado) and not clase.taller_notas_liberadas and not modo_vista_previa

        context.update({
            'clase': clase,
            'taller': taller,
            'preguntas': preguntas_taller,
            'grupos': agrupar_por_bloque(preguntas_taller, get_pregunta=lambda pt: pt.pregunta),
            'intento': intento,
            'entregado': entregado,
            'modo_lectura_socializacion': modo_lectura_socializacion,
            'modo_vista_previa': modo_vista_previa,
            'titulo': f'Taller Presencial: {taller.titulo} — {clase.materia.nombre}'
        })
        return context

    def post(self, request, *args, **kwargs):
        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        taller = clase.taller

        modo_vista_previa = request.user.is_superuser or request.user == clase.profesor
        if modo_vista_previa:
            messages.info(request, "Vista Previa de Docente: Las respuestas introducidas no generan calificaciones ni intentos registrados.")
            return redirect('mis_clases_presenciales')

        if clase.taller_cerrado:
            messages.warning(request, "El profesor ha cerrado la recepción de respuestas para este taller presencial.")
            return redirect('taller_presencial_ejecutar', clase_id=clase.id)

        intento = IntentoTaller.objects.filter(usuario=request.user, taller=taller, clase=clase).first()
        if not intento:
            intento = IntentoTaller.objects.filter(usuario=request.user, taller=taller).first()
        if not intento:
            intento = IntentoTaller.objects.create(
                usuario=request.user,
                taller=taller,
                clase=clase,
                puntaje_porcentaje=0
            )
        elif not intento.clase:
            intento.clase = clase

        preguntas_taller = taller.preguntas_taller.select_related('pregunta').all()
        total_preguntas = preguntas_taller.count()
        respuestas_correctas = 0

        intento.respuestas.all().delete()

        for pt in preguntas_taller:
            pregunta = pt.pregunta
            opcion_id = request.POST.get(f'pregunta_{pregunta.id}')

            if opcion_id:
                try:
                    opcion_sel = Opcion.objects.get(id=opcion_id, pregunta=pregunta)
                    es_cor = opcion_sel.es_correcta
                    if es_cor:
                        respuestas_correctas += 1

                    RespuestaTaller.objects.create(
                        intento=intento,
                        pregunta=pregunta,
                        opcion_seleccionada=opcion_sel,
                        es_correcta=es_cor
                    )
                except Opcion.DoesNotExist:
                    pass

        puntaje = (respuestas_correctas / total_preguntas * 100) if total_preguntas > 0 else 0
        intento.puntaje_porcentaje = puntaje
        intento.fecha_fin = timezone.now()
        intento.clase = clase
        intento.save()

        # Sincronización automática con el objeto Nota de Cartera
        alumno = get_alumno_for_user(request.user)
        if alumno:
            Nota.objects.update_or_create(
                clase=clase,
                alumno=alumno,
                defaults={'nota': round(puntaje, 1)}
            )

        if clase.taller_notas_liberadas:
            messages.success(request, f"¡Taller Presencial Finalizado! Tu calificación obtenida es: {puntaje:.1f}%")
            return redirect('evaluaciones:taller_intento_detail', pk=intento.pk)
        else:
            messages.success(request, "¡Taller Presencial Entregado! Tus respuestas han sido guardadas. El solucionario y notas se liberarán cuando tu profesor inicie la entrega de calificaciones.")
            return redirect('taller_presencial_ejecutar', clase_id=clase.id)


class ClaseTallerControlView(LoginRequiredMixin, TemplateView):
    """
    Panel de Control en Vivo para el Profesor:
    - Visualizar asistentes y entregas en tiempo real.
    - Botón 1: Cerrar Taller (Corte de entregas para pendientes).
    - Botón 2: Liberar / Ocultar Notas y Solucionario.
    """
    template_name = 'academico/clase_taller_control.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        user = request.user

        if not (user.is_superuser or user.is_staff or user == clase.profesor):
            messages.error(request, "Acceso restringido al Panel de Control de Docente.")
            return redirect('mis_clases_presenciales')

        if not clase.taller:
            messages.error(request, "Esta clase presencial no posee un taller asignado.")
            return redirect('profesor_clases', profesor_id=user.id)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        taller = clase.taller

        asistencias = Asistencia.objects.filter(clase=clase, asistio=True).select_related('alumno', 'alumno__usuario')

        estudiantes_status = []
        total_asistentes = asistencias.count()
        total_entregados = 0

        for asis in asistencias:
            alumno = asis.alumno
            u_student = alumno.usuario
            if not u_student:
                u_student = User.objects.filter(username=alumno.identificacion).first()

            intento = None
            if u_student:
                intento = IntentoTaller.objects.filter(usuario=u_student, taller=taller, clase=clase).first()
                if not intento:
                    intento = IntentoTaller.objects.filter(usuario=u_student, taller=taller).first()

            entregado = bool(intento and intento.fecha_fin)
            if entregado:
                total_entregados += 1

            estudiantes_status.append({
                'alumno': alumno,
                'user_student': u_student,
                'entregado': entregado,
                'intento': intento,
            })

        context.update({
            'clase': clase,
            'taller': taller,
            'estudiantes_status': estudiantes_status,
            'total_asistentes': total_asistentes,
            'total_entregados': total_entregados,
            'total_pendientes': max(0, total_asistentes - total_entregados),
            'titulo': f'Control de Taller: {taller.titulo} — {clase.materia.nombre}'
        })
        return context

    def post(self, request, *args, **kwargs):
        clase = get_object_or_404(Clase, pk=self.kwargs['clase_id'])
        taller = clase.taller
        action = request.POST.get('action')

        if action == 'cerrar_taller':
            clase.taller_cerrado = True
            clase.save(update_fields=['taller_cerrado'])

            asistencias = Asistencia.objects.filter(clase=clase, asistio=True).select_related('alumno', 'alumno__usuario')
            for asis in asistencias:
                alumno = asis.alumno
                u_student = alumno.usuario
                if not u_student:
                    u_student = User.objects.filter(username=alumno.identificacion).first()
                if u_student:
                    intento = IntentoTaller.objects.filter(usuario=u_student, taller=taller, clase=clase).first()
                    if not intento:
                        intento = IntentoTaller.objects.filter(usuario=u_student, taller=taller).first()
                    if not intento:
                        intento = IntentoTaller.objects.create(
                            usuario=u_student,
                            taller=taller,
                            clase=clase,
                            puntaje_porcentaje=0
                        )
                    if not intento.fecha_fin:
                        preguntas_taller = taller.preguntas_taller.select_related('pregunta').all()
                        total_p = preguntas_taller.count()
                        correctas = intento.respuestas.filter(es_correcta=True).count()
                        puntaje = (correctas / total_p * 100) if total_p > 0 else 0
                        intento.puntaje_porcentaje = puntaje
                        intento.fecha_fin = timezone.now()
                        intento.clase = clase
                        intento.save()

                        # Sincronización con Nota de Cartera
                        Nota.objects.update_or_create(
                            clase=clase,
                            alumno=alumno,
                            defaults={'nota': round(puntaje, 1)}
                        )

            messages.success(request, "🔴 Taller presencial cerrado. Se forzó la entrega de respuestas para todos los estudiantes asistentes.")

        elif action == 'reabrir_taller':
            clase.taller_cerrado = False
            clase.save(update_fields=['taller_cerrado'])
            messages.info(request, "🟢 Taller presencial reabierto para recibir respuestas.")

        elif action == 'liberar_notas':
            clase.taller_notas_liberadas = True
            clase.save(update_fields=['taller_notas_liberadas'])
            messages.success(request, "🎉 ¡Notas y solucionarios liberados! Los estudiantes asistidos ya pueden ver sus resultados.")

        elif action == 'ocultar_notas':
            clase.taller_notas_liberadas = False
            clase.save(update_fields=['taller_notas_liberadas'])
            messages.warning(request, "🔒 Notas del taller ocultadas temporalmente.")

        return redirect('clase_taller_control', clase_id=clase.id)
