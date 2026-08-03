from django.views.generic import FormView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import render
from django import forms
from django.contrib.auth import get_user_model
import secrets
import string

User = get_user_model()

class AdminPasswordResetForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        label="Seleccionar Usuario",
        widget=forms.Select(attrs={'class': 'form-select block w-full'})
    )

class AdminPasswordResetView(UserPassesTestMixin, FormView):
    template_name = 'usuarios/admin_password_reset.html'
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy('usuarios:admin_reset_password')
    
    def test_func(self):
        return self.request.user.is_superuser
        
    def form_valid(self, form):
        user = form.cleaned_data['user']
        
        # Generar contraseña aleatoria (10 caracteres, letras y números)
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(10))
        
        # Asignarla
        user.set_password(new_password)
        user.save()
        
        # Renderear el template con el resultado directamente para que el admin copie la contraseña
        context = self.get_context_data(form=form)
        context['reset_success'] = True
        context['affected_user'] = user
        context['new_password'] = new_password
        return render(self.request, self.template_name, context)

from .forms import RegistroInternoForm
from suscripciones.models import Subscription
from django.contrib import messages

class RegistroUsuarioView(UserPassesTestMixin, FormView):
    template_name = 'usuarios/registro_interno.html'
    form_class = RegistroInternoForm
    success_url = reverse_lazy('usuarios:registro_interno')

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def form_valid(self, form):
        from django.contrib.auth.models import Group
        
        user = form.save(commit=False)
        user.creador = self.request.user
        
        # Asignar nivel de Staff basado en el Grupo elegido
        # (se asigna después del save inicial para poder evaluar grupos)
        # Generar contraseña temporal segura
        alphabet = string.ascii_letters + string.digits
        temporal_password = ''.join(secrets.choice(alphabet) for i in range(10))
        user.set_password(temporal_password)
        user.save()

        # Asignación de Grupos de Permisos según el tipo_registro seleccionado en el formulario
        tipo = form.cleaned_data.get('tipo_registro', '')
        try:
            if tipo == 'teacher':
                teacher_group, _ = Group.objects.get_or_create(name='Teacher')
                user.groups.add(teacher_group)
                user.is_staff = True
                user.save(update_fields=['is_staff'])
            elif tipo == 'student':
                student_group, _ = Group.objects.get_or_create(name='Student')
                user.groups.add(student_group)
            elif tipo == 'virtual_student':
                virtual_student_group, _ = Group.objects.get_or_create(name='VirtualStudent')
                user.groups.add(virtual_student_group)
            elif tipo == 'staff':
                user.is_staff = True
                user.save(update_fields=['is_staff'])
        except Exception:
            pass

        # Si pertenece a grupos de estudiante, crear suscripción
        es_estudiante_registrado = user.groups.filter(name__in=['Student', 'VirtualStudent']).exists()
        es_virtual = user.groups.filter(name='VirtualStudent').exists()

        if es_estudiante_registrado:
            Subscription.objects.create(
                user=user,
                creador=self.request.user,
                start_date=form.cleaned_data['start_date'],
                end_date=form.cleaned_data['end_date']
            )
            formato_rol = "Estudiante Virtual" if es_virtual else "Estudiante"
            messages.success(self.request, f"{formato_rol} {user.username} registrado con éxito. Contraseña temporal: {temporal_password}. Suscripción activada.")
        else:
            tipo_label = "Docente" if user.es_docente else "Usuario"
            messages.success(self.request, f"{tipo_label} {user.username} registrado con éxito. Contraseña temporal: {temporal_password}.")

        # Renderizar la respuesta con una bandera de éxito para que copien la password
        context = self.get_context_data(form=self.form_class())
        context['registration_success'] = True
        context['new_user'] = user
        context['temp_password'] = temporal_password
        return render(self.request, self.template_name, context)

from django.views.generic import TemplateView
from django.shortcuts import redirect

class LandingView(TemplateView):
    template_name = 'landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            user = request.user
            # 1. Docentes (no superusuario) -> Mis Clases
            if user.es_docente and not user.is_superuser:
                return redirect('profesor_clases', profesor_id=user.id)
            
            # 2. Staff / Cartera / Secretarías / Coordinadores / Admin -> Alumnos list
            if user.is_superuser or user.is_staff or user.es_personal_gestion:
                return redirect('alumnos_list')
                
            # 3. Estudiantes -> Aula Virtual
            return redirect('curriculo:programa_list')
        return super().dispatch(request, *args, **kwargs)

from django.views.generic import ListView, CreateView
from django.contrib.auth.models import Group
from django.utils import timezone
from .models import VentanaRegistro
from .forms import VentanaRegistroForm, RegistroPublicoForm
from dateutil.relativedelta import relativedelta

class VentanaRegistroListView(UserPassesTestMixin, ListView):
    model = VentanaRegistro
    template_name = 'usuarios/ventanas_list.html'
    context_object_name = 'ventanas'
    
    def test_func(self):
        return self.request.user.is_superuser

class VentanaRegistroCreateView(UserPassesTestMixin, CreateView):
    model = VentanaRegistro
    form_class = VentanaRegistroForm
    template_name = 'usuarios/ventana_form.html'
    success_url = reverse_lazy('usuarios:ventanas_list')
    
    def test_func(self):
        return self.request.user.is_superuser
        
    def form_valid(self, form):
        form.instance.creador = self.request.user
        return super().form_valid(form)

class RegistroPublicoView(FormView):
    template_name = 'usuarios/registro_publico.html'
    form_class = RegistroPublicoForm
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        # Allow superusers to preview it even if closed (optional) or restrict strictly
        active_window = VentanaRegistro.objects.filter(
            fecha_inicio__lte=timezone.now(),
            fecha_fin__gte=timezone.now()
        ).exists()
        
        if not active_window:
            return render(request, 'usuarios/registro_cerrado.html', status=403)
            
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.is_staff = False  # Strictly override just in case
        user.save()

        # Asignación de grupo según tipo_registro
        tipo = form.cleaned_data.get('tipo_registro', 'student')
        try:
            if tipo == 'student':
                group, _ = Group.objects.get_or_create(name='Student')
                user.groups.add(group)
            elif tipo == 'virtual_student':
                group, _ = Group.objects.get_or_create(name='VirtualStudent')
                user.groups.add(group)
        except Exception:
            pass

        # Calculate subscription dates based on active config or fallback
        from suscripciones.models import SubscriptionConfig
        config = SubscriptionConfig.objects.filter(active=True).first()
        
        if config:
            start_date = config.default_start_date
            end_date = config.default_end_date
        else:
            # Fallback if no active config exists
            start_date = timezone.now().date()
            end_date = start_date + relativedelta(years=1)
        
        Subscription.objects.create(
            user=user,
            creador=None,  # Was registered by themselves
            start_date=start_date,
            end_date=end_date
        )

        tipo_label = "Estudiante Virtual" if user.groups.filter(name='VirtualStudent').exists() else "Estudiante"
        messages.success(self.request, f"¡Tu cuenta como {tipo_label} ha sido creada! Ya puedes iniciar sesión.")
        return super().form_valid(form)

from django.conf import settings
from twilio.rest import Client
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from .models import WhatsAppResetCode
from .forms import WhatsAppResetRequestForm, WhatsAppResetVerifyForm, WhatsAppResetPasswordForm
import os

class WhatsAppResetRequestView(FormView):
    template_name = 'registration/whatsapp_reset_request.html'
    form_class = WhatsAppResetRequestForm
    success_url = reverse_lazy('usuarios:whatsapp_reset_verify')

    def form_valid(self, form):
        telefono = form.cleaned_data['telefono']
        users = User.objects.filter(telefono=telefono)
        count = users.count()

        if count == 0:
            messages.error(self.request, "El número no está registrado en el sistema.")
            return self.form_invalid(form)
        elif count > 1:
            messages.error(self.request, "Hay varios usuarios con este número. Por favor, contacta a soporte.")
            return self.form_invalid(form)
        
        user = users.first()
        code = get_random_string(length=6, allowed_chars='0123456789')
        
        # Eliminar códigos antiguos no usados de este usuario (opcional para limpieza)
        WhatsAppResetCode.objects.filter(user=user, is_used=False).delete()
        WhatsAppResetCode.objects.create(user=user, code=code)

        try:
            # Twilio envio
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            twilio_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
            
            if account_sid and auth_token and twilio_number:
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    from_=f'whatsapp:{twilio_number}',
                    body=f'Tu código de seguridad para PreICFES Virtual Victor Valdez es: {code}. Este código expirará en 5 minutos.',
                    to=f'whatsapp:+57{telefono}'
                )
                messages.success(self.request, f"Te hemos enviado un código de 6 dígitos a tu WhatsApp terminado en {telefono[-4:]}.")
            else:
                 messages.warning(self.request, "Variables de entorno de Twilio no configuradas. " + f"Código en modo local: {code}")
        except Exception as e:
            messages.error(self.request, f"Error al enviar el WhatsApp: {str(e)}")
            return self.form_invalid(form)

        # Guardar teléfono en sesión para el siguiente paso
        self.request.session['reset_phone'] = telefono
        return super().form_valid(form)


class WhatsAppResetVerifyView(FormView):
    template_name = 'registration/whatsapp_reset_verify.html'
    form_class = WhatsAppResetVerifyForm
    success_url = reverse_lazy('usuarios:whatsapp_reset_password')

    def dispatch(self, request, *args, **kwargs):
        if 'reset_phone' not in request.session:
            messages.error(request, "Por favor, inicia la solicitud de recuperación primero.")
            return redirect('usuarios:whatsapp_reset_request')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['telefono'] = self.request.session.get('reset_phone')
        return context

    def form_valid(self, form):
        code_input = form.cleaned_data['code']
        telefono = self.request.session.get('reset_phone')
        user = User.objects.filter(telefono=telefono).first()

        if not user:
            messages.error(self.request, "Error interno. Usuario no encontrado.")
            return self.form_invalid(form)

        reset_code = WhatsAppResetCode.objects.filter(user=user, code=code_input).first()

        if reset_code and reset_code.is_valid():
            reset_code.is_used = True
            reset_code.save()
            self.request.session['reset_verified'] = True
            messages.success(self.request, "Código verificado correctamente.")
            return super().form_valid(form)
        else:
            messages.error(self.request, "El código es incorrecto o ha expirado.")
            return self.form_invalid(form)


class WhatsAppResetPasswordView(FormView):
    template_name = 'registration/whatsapp_reset_password.html'
    form_class = WhatsAppResetPasswordForm
    success_url = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('reset_verified') or not request.session.get('reset_phone'):
            messages.error(request, "Debes verificar tu código primero.")
            return redirect('usuarios:whatsapp_reset_request')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        telefono = self.request.session.get('reset_phone')
        user = User.objects.filter(telefono=telefono).first()

        if user:
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(self.request, "¡Tu contraseña se ha restablecido exitosamente! Ya puedes iniciar sesión.")
            # Limpiar sesión
            del self.request.session['reset_phone']
            del self.request.session['reset_verified']
            return super().form_valid(form)
        else:
            messages.error(self.request, "Usuario no válido.")
            return self.form_invalid(form)


from django.views.generic import TemplateView
from django.db.models import Q, Max, Avg
from curriculo.models.core import Asistencia
from evaluaciones.models import Taller, IntentoTaller, IntentoSimulacro

class VigilarActividadView(UserPassesTestMixin, TemplateView):
    template_name = 'usuarios/vigilar_actividad.html'

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        user_id = self.request.GET.get('user_id', '').strip()
        
        # Filtrar solo usuarios que sean estudiantes o estudiantes virtuales
        students_qs = User.objects.filter(groups__name__in=['Student', 'VirtualStudent'], is_active=True).distinct()
        
        if q:
            students_qs = students_qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(numero_documento__icontains=q) |
                Q(telefono__icontains=q)
            )
            
        context['q'] = q
        context['estudiantes'] = students_qs[:50]  # Limitar para evitar lentitud
        
        selected_user = None
        if user_id:
            try:
                selected_user = User.objects.filter(id=user_id, groups__name__in=['Student', 'VirtualStudent']).first()
            except User.DoesNotExist:
                pass
        elif students_qs.count() == 1 and q:
            # Si hay exactamente un resultado y el usuario buscó activamente, lo seleccionamos
            selected_user = students_qs.first()
            
        if selected_user:
            context['selected_user'] = selected_user
            
            # 1. Asistencias
            asistencias = Asistencia.objects.filter(alumno=selected_user).select_related('clase', 'clase__modulo').order_by('-clase__fecha')
            total_asistencias = asistencias.count()
            presentes = asistencias.filter(asistio=True).count()
            porcentaje_asistencia = (presentes / total_asistencias * 100) if total_asistencias > 0 else 0.0
            
            context['asistencias'] = asistencias
            context['total_asistencias'] = total_asistencias
            context['presentes'] = presentes
            context['porcentaje_asistencia'] = round(porcentaje_asistencia, 1)
            
            # 2. Talleres Hechos (Completados)
            talleres_publicados = Taller.objects.filter(estado='publicado').select_related('modulo', 'tema__materia')
            total_talleres = talleres_publicados.count()
            
            # Intentos completados
            intentos_taller = IntentoTaller.objects.filter(
                usuario=selected_user,
                fecha_fin__isnull=False
            )
            
            # Agrupar por taller para obtener el mejor puntaje de cada uno
            mejores_intentos = intentos_taller.values('taller_id').annotate(
                mejor_puntaje=Max('puntaje_porcentaje')
            )
            puntajes_talleres = {item['taller_id']: item['mejor_puntaje'] for item in mejores_intentos}
            
            talleres_hechos = len(puntajes_talleres)
            porcentaje_talleres = (talleres_hechos / total_talleres * 100) if total_talleres > 0 else 0.0
            
            if puntajes_talleres:
                promedio_talleres = sum(puntajes_talleres.values()) / len(puntajes_talleres)
            else:
                promedio_talleres = 0.0
                
            # Construir lista detallada de talleres
            talleres_info = []
            for taller in talleres_publicados:
                mejor_p = puntajes_talleres.get(taller.id, None)
                intentos_count = intentos_taller.filter(taller=taller).count()
                talleres_info.append({
                    'taller': taller,
                    'completado': mejor_p is not None,
                    'mejor_puntaje': mejor_p,
                    'intentos_count': intentos_count,
                })
                
            context['talleres_info'] = talleres_info
            context['total_talleres'] = total_talleres
            context['talleres_hechos'] = talleres_hechos
            context['porcentaje_talleres'] = round(porcentaje_talleres, 1)
            context['promedio_talleres'] = round(promedio_talleres, 1)
            
            # 3. Simulacros
            intentos_simulacro = IntentoSimulacro.objects.filter(
                usuario=selected_user,
                fecha_fin__isnull=False
            ).select_related('simulacro').order_by('-fecha_inicio')
            
            context['intentos_simulacro'] = intentos_simulacro
            total_simulacros = intentos_simulacro.count()
            if total_simulacros > 0:
                promedio_simulacros = intentos_simulacro.aggregate(Avg('puntaje_global'))['puntaje_global__avg'] or 0.0
            else:
                promedio_simulacros = 0.0
                
            context['total_simulacros'] = total_simulacros
            context['promedio_simulacros'] = round(promedio_simulacros, 1)
            
        return context

class ProfesorListView(UserPassesTestMixin, ListView):
    model = User
    template_name = 'usuarios/profesor_list.html'
    context_object_name = 'profesores'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_queryset(self):
        queryset = User.objects.filter(
            Q(groups__name__in=['Profesor', 'Teacher']) |
            Q(programas_docente__isnull=False) |
            Q(clases__isnull=False)
        ).exclude(
            groups__name__in=['Student', 'VirtualStudent']
        ).distinct()
        
        user = self.request.user
        if user.is_superuser:
            pass
        elif user.groups.filter(name='CoordinadorDepartamental').exists():
            if hasattr(user, 'departamento') and user.departamento:
                queryset = queryset.filter(municipio__departamento=user.departamento)
        else:
            if hasattr(user, 'municipio') and user.municipio:
                queryset = queryset.filter(municipio=user.municipio)

        municipio_id = self.request.GET.get('municipio')
        if municipio_id:
            queryset = queryset.filter(municipio_id=municipio_id)
            
        q = self.request.GET.get('q', '').strip()
        if q:
            words = q.split()
            search_query = Q()
            for word in words:
                search_query &= (
                    Q(first_name__icontains=word) |
                    Q(last_name__icontains=word) |
                    Q(username__icontains=word) |
                    Q(numero_documento__icontains=word) |
                    Q(telefono__icontains=word) |
                    Q(email__icontains=word)
                )
            queryset = queryset.filter(search_query)
            
        return queryset.order_by('first_name', 'last_name')

    def get_context_data(self, **kwargs):
        from ubicaciones.models import Municipio
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Listado de Profesores'
        user = self.request.user
        if user.is_superuser:
            context['municipios'] = Municipio.objects.all()
        elif user.groups.filter(name='CoordinadorDepartamental').exists() and hasattr(user, 'departamento') and user.departamento:
            context['municipios'] = Municipio.objects.filter(departamento=user.departamento)
        else:
            context['municipios'] = Municipio.objects.filter(id=user.municipio.id) if hasattr(user, 'municipio') and user.municipio else Municipio.objects.none()
        return context


from django.views.generic import DetailView
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, Http404
from .forms import CertificadoTrabajoForm

class ProfesorDetailView(UserPassesTestMixin, DetailView):
    model = User
    template_name = 'usuarios/profesor_detail.html'
    context_object_name = 'profesor'

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Detalles del Profesor: {self.object.get_full_name() or self.object.username}'
        puede_generar_certificado = (
            self.request.user.is_superuser or
            self.request.user.groups.filter(name='SecretariaAcademica').exists()
        )
        context['puede_generar_certificado'] = puede_generar_certificado
        return context


class CertificadoTrabajoFormView(UserPassesTestMixin, FormView):
    template_name = 'usuarios/certificado_trabajo_form.html'
    form_class = CertificadoTrabajoForm

    def test_func(self):
        return (
            self.request.user.is_superuser or
            self.request.user.groups.filter(name='SecretariaAcademica').exists()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profesor_id = self.kwargs.get('profesor_id')
        profesor = get_object_or_404(User, pk=profesor_id)
        context['profesor'] = profesor
        return context

    def form_valid(self, form):
        profesor_id = self.kwargs.get('profesor_id')
        fecha_inicio = form.cleaned_data['fecha_inicio']
        fecha_fin = form.cleaned_data['fecha_fin']
        url = reverse('generar_certificado_trabajo', kwargs={'profesor_id': profesor_id})
        url += f'?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}'
        return redirect(url)


import os
from datetime import datetime
from django.views import View
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from .models import Firma
from academico.models import Clase

class GenerarCertificadoTrabajoView(UserPassesTestMixin, View):
    def test_func(self):
        return (
            self.request.user.is_superuser or
            self.request.user.groups.filter(name='SecretariaAcademica').exists()
        )

    def get(self, request, profesor_id):
        profesor = get_object_or_404(User, pk=profesor_id)
        if not profesor.es_docente and not profesor.is_staff:
            raise Http404("El usuario no es un profesor registrado")

        fecha_inicio_str = request.GET.get('fecha_inicio')
        fecha_fin_str = request.GET.get('fecha_fin')

        if not fecha_inicio_str or not fecha_fin_str:
            return redirect('certificado_trabajo_form', profesor_id=profesor_id)

        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        except ValueError:
            return redirect('certificado_trabajo_form', profesor_id=profesor_id)

        response = HttpResponse(content_type='application/pdf')
        filename = f"certificado_trabajo_{profesor.username}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        doc = SimpleDocTemplate(
            response,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='CenterText', alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='JustifyText', alignment=TA_JUSTIFY))
        styles.add(ParagraphStyle(name='SmallCenterText', alignment=TA_CENTER, fontSize=8))
        styles['Title'].alignment = TA_CENTER
        styles['Title'].fontSize = 14
        styles['Title'].fontName = 'Helvetica-Bold'

        elements = []
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=1.5*inch, height=1.5*inch))
            elements.append(Spacer(1, 15))

        fecha_actual = timezone.now().date()
        meses_es = {
            'January': 'enero', 'February': 'febrero', 'March': 'marzo',
            'April': 'abril', 'May': 'mayo', 'June': 'junio',
            'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
            'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
        }
        mes_actual_es = meses_es.get(fecha_actual.strftime('%B'), fecha_actual.strftime('%B'))

        elements.append(Paragraph('<b>EL PRE ICFES VICTOR VALDEZ</b>', styles['Title']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph('<b>NIT - 9012725987</b>', styles['Title']))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph('<b>CERTIFICA QUE</b>', styles['CenterText']))
        elements.append(Spacer(1, 20))

        mes_inicio_es = meses_es.get(fecha_inicio.strftime('%B'), fecha_inicio.strftime('%B'))
        fecha_inicio_texto = f"{fecha_inicio.day} de {mes_inicio_es} de {fecha_inicio.year}"
        mes_fin_es = meses_es.get(fecha_fin.strftime('%B'), fecha_fin.strftime('%B'))
        fecha_fin_texto = f"{fecha_fin.day} de {mes_fin_es} de {fecha_fin.year}"

        materias_profesor = Clase.objects.filter(
            profesor=profesor,
            estado='vista'
        ).values_list('materia__nombre', flat=True).distinct()

        materias_texto = "NO DISPONIBLE"
        if materias_profesor:
            materias_lista = list(materias_profesor)
            if len(materias_lista) == 1:
                materias_texto = materias_lista[0].upper()
            elif len(materias_lista) == 2:
                materias_texto = f"{materias_lista[0].upper()} Y {materias_lista[1].upper()}"
            else:
                materias_texto = ", ".join([m.upper() for m in materias_lista[:-1]]) + f" Y {materias_lista[-1].upper()}"

        nombre_completo = profesor.get_full_name()
        if not nombre_completo.strip():
            nombre_completo = profesor.username

        doc_tipo = profesor.get_tipo_documento_display() if hasattr(profesor, 'get_tipo_documento_display') else 'documento de identidad'
        doc_num = profesor.numero_documento if profesor.numero_documento else 'No disponible'

        texto_certificado1 = f"Que el(la) señor(a) <b>{nombre_completo}</b>, identificado(a) con {doc_tipo} N° <b>{doc_num}</b> se encuentra prestando su servicio como docente de horas cátedras en el área de <b>{materias_texto}</b>, desde el <b>{fecha_inicio_texto}</b> hasta el <b>{fecha_fin_texto}</b>."
        elements.append(Paragraph(texto_certificado1, styles['JustifyText']))
        elements.append(Spacer(1, 20))

        texto_certificado2 = "Durante este tiempo, ha demostrado ser un profesional excepcional y comprometido con la institución. Su capacidad para enseñar y motivar a los estudiantes es destacable."
        elements.append(Paragraph(texto_certificado2, styles['JustifyText']))
        elements.append(Spacer(1, 30))

        elements.append(Paragraph(
            f"Para mayor constancia se firma y se sella a los ({fecha_actual.day}) días del mes de {mes_actual_es} de {fecha_actual.year}.",
            styles['JustifyText']
        ))
        elements.append(Spacer(1, 40))

        try:
            coordinador = request.user
            firma = Firma.objects.get(usuario=coordinador)
            if firma.imagen and os.path.exists(firma.imagen.path):
                firma_img = Image(firma.imagen.path)
                firma_img.drawHeight = 0.6*inch
                firma_img.drawWidth = 2.2*inch
                elements.append(firma_img)
                elements.append(Spacer(1, 5))
            else:
                elements.append(Paragraph("___________________________________________", styles['CenterText']))
        except Exception:
            elements.append(Paragraph("___________________________________________", styles['CenterText']))

        nombre_completo_usuario = f"{request.user.first_name} {request.user.last_name}"
        if not nombre_completo_usuario.strip():
            nombre_completo_usuario = request.user.username

        elements.append(Paragraph(f"<b>{nombre_completo_usuario}</b>", styles['CenterText']))
        elements.append(Paragraph("<b>COORDINADOR(A) ACADÉMICO(A) PRE ICFES VICTOR VALDEZ</b>", styles['CenterText']))

        telefono = request.user.telefono if request.user.telefono else ""
        if telefono:
            elements.append(Paragraph(f"Cel: {telefono}", styles['CenterText']))
        elements.append(Spacer(1, 25))

        elements.append(Paragraph("<b>VALDEZ Y ANDRADE SOLUCIONES S.A.S</b>", styles['SmallCenterText']))
        elements.append(Paragraph("<b>NIT 901.272.598 - 7</b>", styles['SmallCenterText']))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph("_______________________________________________________________", styles['CenterText']))
        elements.append(Paragraph("<b>CRA. 60A # 29 - 47 BARRIO LOS ANGELES</b>", styles['CenterText']))

        doc.build(elements)
        return response


