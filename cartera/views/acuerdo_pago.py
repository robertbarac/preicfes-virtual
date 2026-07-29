from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.utils import timezone
from cartera.models import AcuerdoPago, Cuota
from cartera.forms import AcuerdoPagoForm, AcuerdoPagoFilterForm

class AcuerdoPagoListView(LoginRequiredMixin, ListView):
    model = AcuerdoPago
    template_name = 'cartera/acuerdo_pago_list.html'
    context_object_name = 'acuerdos'
    paginate_by = 30

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

    
    def get_queryset(self):
        hoy = timezone.localtime(timezone.now()).date()
        # Actualizar estados de acuerdos emitidos
        acuerdos_pendientes = AcuerdoPago.objects.filter(estado='emitido')
        for acuerdo in acuerdos_pendientes:
            if acuerdo.cuota.estado in ['pagada', 'pagada_parcial']:
                acuerdo.estado = 'cumplido'
                acuerdo.save()
            elif acuerdo.fecha_prometida_pago < hoy:
                acuerdo.estado = 'incumplido'
                acuerdo.save()

        # Queryset base
        queryset = AcuerdoPago.objects.select_related(
            'cuota__deuda__alumno',
            'cuota__deuda__alumno__municipio__departamento'
        ).filter(
            cuota__deuda__alumno__estado='activo'
        ).order_by('fecha_prometida_pago')

        # Filtrado basado en roles de usuario
        user = self.request.user
        if not user.is_superuser:
            if user.groups.filter(name='CoordinadorDepartamental').exists() and user.departamento:
                queryset = queryset.filter(cuota__deuda__alumno__municipio__departamento=user.departamento)
            elif user.groups.filter(name='SecretariaCartera').exists() and user.municipio:
                queryset = queryset.filter(cuota__deuda__alumno__municipio=user.municipio)
            elif getattr(user, 'is_observador', False) and hasattr(user, 'sede') and user.sede:
                queryset = queryset.filter(cuota__deuda__alumno__grupo_actual__salon__sede=user.sede)
            else:
                # Si no es superusuario y no tiene rol con ubicación, no muestra nada
                return queryset.none()

        # Aplicar filtros del formulario
        form = AcuerdoPagoFilterForm(self.request.GET)
        if form.is_valid():
            departamento = form.cleaned_data.get('departamento')
            municipio = form.cleaned_data.get('municipio')
            estado = form.cleaned_data.get('estado')
            dias_restantes = form.cleaned_data.get('dias_restantes')

            if municipio:
                queryset = queryset.filter(cuota__deuda__alumno__municipio=municipio)
            elif departamento:
                queryset = queryset.filter(cuota__deuda__alumno__municipio__departamento=departamento)

            if dias_restantes is not None:
                hoy = timezone.localtime(timezone.now()).date()
                fecha_limite = hoy + timezone.timedelta(days=dias_restantes)
                queryset = queryset.filter(fecha_prometida_pago__gte=hoy, fecha_prometida_pago__lte=fecha_limite)
            if estado:
                queryset = queryset.filter(estado=estado)
        
        return queryset

    def get_context_data(self, **kwargs):
        from ubicaciones.models import Municipio, Departamento
        context = super().get_context_data(**kwargs)
        user = self.request.user
        hoy = timezone.localtime(timezone.now()).date()
        
        for acuerdo in context['acuerdos']:
            delta = acuerdo.fecha_prometida_pago - hoy
            acuerdo.dias_faltantes = delta.days

        # Inicializar y configurar el formulario de filtros
        form = AcuerdoPagoFilterForm(self.request.GET)
        if not user.is_superuser:
            if user.groups.filter(name='CoordinadorDepartamental').exists() and user.departamento:
                form.fields['departamento'].queryset = Departamento.objects.filter(id=user.departamento.id)
                form.fields['municipio'].queryset = Municipio.objects.filter(departamento=user.departamento)
            elif user.municipio:
                form.fields['departamento'].queryset = Departamento.objects.filter(id=user.municipio.departamento.id)
                form.fields['municipio'].queryset = Municipio.objects.filter(id=user.municipio.id)

        context['filter_form'] = form
        context['is_coordinador'] = user.groups.filter(name='CoordinadorDepartamental').exists()
        return context

class AcuerdoPagoCreateView(LoginRequiredMixin, CreateView):
    model = AcuerdoPago
    form_class = AcuerdoPagoForm
    template_name = 'cartera/acuerdo_pago_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cuota_pk'] = self.kwargs.get('cuota_pk')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cuota'] = get_object_or_404(Cuota, pk=self.kwargs.get('cuota_pk'))
        return context

    def get_success_url(self):
        return reverse_lazy('cartera:acuerdo_pago_list')


class AcuerdoPagoUpdateView(LoginRequiredMixin, UpdateView):
    model = AcuerdoPago
    form_class = AcuerdoPagoForm
    template_name = 'cartera/acuerdo_pago_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # self.object es el acuerdo de pago que se está editando
        context['cuota'] = self.object.cuota
        return context

    def get_success_url(self):
        return reverse_lazy('cartera:acuerdo_pago_list')
