from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import PreVenta, Incidencia, IncidenciaImagen
from .forms import PreVentaForm, IncidenciaForm

Usuario = get_user_model()

class PreVentaListView(LoginRequiredMixin, ListView):
    model = PreVenta
    template_name = 'ventas/preventa_list.html'
    context_object_name = 'preventas'
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = PreVenta.objects.all()
        else:
            queryset = PreVenta.objects.filter(user=user)

        # Filtros de búsqueda (q)
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(nombre_padre_madre__icontains=q) |
                Q(nombre_estudiante__icontains=q) |
                Q(telefono__icontains=q)
            )

        # Filtro de vendedor (solo para superusuarios)
        if user.is_superuser:
            vendedor_id = self.request.GET.get('vendedor', '')
            if vendedor_id:
                queryset = queryset.filter(user_id=vendedor_id)
            
            municipio_id = self.request.GET.get('municipio', '')
            if municipio_id:
                queryset = queryset.filter(user__municipio_id=municipio_id)

        return queryset.select_related('user', 'user__municipio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        
        # Si es superusuario, pasamos todos los vendedores y municipios que tienen registros
        if self.request.user.is_superuser:
            from ubicaciones.models import Municipio
            # Obtener usuarios que son autores de preventas
            vendedores_ids = PreVenta.objects.values_list('user', flat=True).distinct()
            context['vendedores'] = Usuario.objects.filter(id__in=vendedores_ids)
            context['selected_vendedor'] = self.request.GET.get('vendedor', '')
            
            # Obtener municipios asociados a dichos vendedores
            municipios_ids = Usuario.objects.filter(id__in=vendedores_ids).exclude(municipio=None).values_list('municipio', flat=True).distinct()
            context['municipios'] = Municipio.objects.filter(id__in=municipios_ids)
            context['selected_municipio'] = self.request.GET.get('municipio', '')
            
        return context


class PreVentaDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = PreVenta
    template_name = 'ventas/preventa_detail.html'
    context_object_name = 'preventa'

    def test_func(self):
        obj = self.get_object()
        return self.request.user.is_superuser or obj.user == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Traer todas las incidencias asociadas
        context['incidencias'] = self.object.incidencias.all()
        context['ahora'] = timezone.localtime(timezone.now())
        return context


class PreVentaCreateView(LoginRequiredMixin, CreateView):
    model = PreVenta
    form_class = PreVentaForm
    template_name = 'ventas/preventa_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Registrar Nueva Preventa'
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Proceso de preventa registrado exitosamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('ventas:preventa_detail', kwargs={'pk': self.object.pk})


class PreVentaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = PreVenta
    form_class = PreVentaForm
    template_name = 'ventas/preventa_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Datos de Preventa'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Preventa actualizada exitosamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('ventas:preventa_detail', kwargs={'pk': self.object.pk})


class PreVentaDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = PreVenta
    template_name = 'ventas/preventa_confirm_delete.html'
    success_url = reverse_lazy('ventas:preventa_list')

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        messages.success(self.request, 'Proceso de preventa eliminado exitosamente.')
        return super().post(request, *args, **kwargs)


# ==========================================
# VISTAS DE INCIDENCIAS
# ==========================================

class IncidenciaCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Incidencia
    form_class = IncidenciaForm
    template_name = 'ventas/incidencia_form.html'

    def get_preventa(self):
        return get_object_or_404(PreVenta, pk=self.kwargs['preventa_pk'])

    def test_func(self):
        preventa = self.get_preventa()
        return self.request.user.is_superuser or preventa.user == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['preventa'] = self.get_preventa()
        context['titulo'] = 'Registrar Incidencia del Día'
        return context

    def form_valid(self, form):
        preventa = self.get_preventa()
        form.instance.preventa = preventa
        form.instance.user = self.request.user
        form.instance.fecha = timezone.now()
        
        response = super().form_valid(form)
        
        # Procesar y guardar múltiples imágenes de evidencia
        files = self.request.FILES.getlist('imagen')
        for f in files:
            IncidenciaImagen.objects.create(incidencia=self.object, imagen=f)
            
        messages.success(self.request, 'Incidencia agregada correctamente.')
        return response

    def get_success_url(self):
        return reverse('ventas:preventa_detail', kwargs={'pk': self.kwargs['preventa_pk']})


class IncidenciaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Incidencia
    form_class = IncidenciaForm
    template_name = 'ventas/incidencia_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permiso para editar incidencias. Solo los administradores pueden realizar esta acción.')
        return redirect('ventas:preventa_detail', pk=self.get_object().preventa.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['preventa'] = self.object.preventa
        context['titulo'] = 'Editar Incidencia'
        return context

    def form_valid(self, form):
        # Asegurar que no alteren la fecha/hora ni el autor original
        incidencia_orig = self.get_object()
        form.instance.fecha = incidencia_orig.fecha
        form.instance.user = incidencia_orig.user
        
        response = super().form_valid(form)
        
        # Procesar y guardar imágenes adicionales en caso de edición
        files = self.request.FILES.getlist('imagen')
        for f in files:
            IncidenciaImagen.objects.create(incidencia=self.object, imagen=f)
            
        messages.success(self.request, 'Incidencia actualizada correctamente.')
        return response

    def get_success_url(self):
        return reverse('ventas:preventa_detail', kwargs={'pk': self.object.preventa.pk})


class IncidenciaDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Incidencia
    template_name = 'ventas/incidencia_confirm_delete.html'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permiso para eliminar incidencias. Solo los administradores pueden realizar esta acción.')
        return redirect('ventas:preventa_detail', pk=self.get_object().preventa.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['preventa'] = self.object.preventa
        return context

    def post(self, request, *args, **kwargs):
        preventa_pk = self.get_object().preventa.pk
        messages.success(self.request, 'Incidencia eliminada exitosamente.')
        # Proceder con la eliminación
        response = super().post(request, *args, **kwargs)
        return response

    def get_success_url(self):
        return reverse('ventas:preventa_detail', kwargs={'pk': self.object.preventa.pk})
