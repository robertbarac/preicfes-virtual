# views/resultados_diagnostico.py

from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from academico.models import Grupo
from ubicaciones.models import Sede
from ..models import SimulacroDiagnostico, ResultadoSimulacroDiagnostico
from .resultados import PermisosResultadosMixin


class ResultadosDiagnosticoListView(LoginRequiredMixin, PermisosResultadosMixin, ListView):
    model = ResultadoSimulacroDiagnostico
    template_name = 'simulacros/resultados_diagnostico_grupo.html'
    context_object_name = 'resultados'

    def get_queryset(self):
        qs = super().get_queryset()

        sede_id = self.request.GET.get('sede')
        grupo_id = self.request.GET.get('grupo')
        simulacro_id = self.request.GET.get('simulacro')
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')

        if sede_id:
            qs = qs.filter(alumno__grupo_actual__salon__sede_id=sede_id)
        if grupo_id:
            qs = qs.filter(alumno__grupo_actual_id=grupo_id)
        if simulacro_id:
            qs = qs.filter(simulacro_id=simulacro_id)
        if fecha_inicio:
            qs = qs.filter(fecha_realizacion__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_realizacion__lte=fecha_fin)

        return qs.select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('alumno__primer_apellido', 'alumno__segundo_apellido')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sedes'] = Sede.objects.all()
        context['grupos'] = Grupo.objects.all()
        context['simulacros'] = SimulacroDiagnostico.objects.all()
        context['es_diagnostico'] = True
        return context
