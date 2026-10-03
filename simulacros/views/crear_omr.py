import os
import tempfile
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.core.exceptions import ValidationError

from ..models import (
    Simulacro, SimulacroDiagnostico,
    _DEFAULT_COMPONENTES_S1, _DEFAULT_COMPONENTES_S2, _DEFAULT_COMPONENTES_SD
)
from ..procesar_simulacro import (
    extraer_tiras_individuales, extraer_tiras_diagnostico, LONGITUDES_ESPERADAS
)


def _guardar_temp_file(uploaded_file):
    """Guarda un archivo subido en el directorio temporal y retorna su ruta."""
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in uploaded_file.chunks():
        tmp.write(chunk)
    tmp.close()
    return tmp.name


class CrearSimulacroOMRView(LoginRequiredMixin, View):
    """Paso 1: Subir imagen(es) de la hoja modelo para escanear con OMR."""
    template_name = 'simulacros/crear_omr_subir.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        tipo = request.POST.get('tipo', 'completo')

        if tipo == 'completo':
            file_s1 = request.FILES.get('imagen_s1')
            file_s2 = request.FILES.get('imagen_s2')

            if not file_s1 or not file_s2:
                messages.error(request, "Para el simulacro completo debes subir ambas hojas modelo: Sesión 1 y Sesión 2.")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})

            path_s1 = _guardar_temp_file(file_s1)
            path_s2 = _guardar_temp_file(file_s2)

            try:
                res = extraer_tiras_individuales(path_s1, path_s2, user=request.user)
            finally:
                if os.path.exists(path_s1): os.remove(path_s1)
                if os.path.exists(path_s2): os.remove(path_s2)

            if res.get('error'):
                messages.warning(request, f"Advertencia OMR: {res['error']}")

            request.session['clave_omr_data'] = {
                'tipo': 'completo',
                's1': res['s1'],
                's2': res['s2'],
                'error': res.get('error'),
            }
            return redirect('simulacros:revisar_clave_omr')

        elif tipo == 'diagnostico':
            file_sd = request.FILES.get('imagen_sd')
            if not file_sd:
                messages.error(request, "Debes subir la hoja modelo del Simulacro Diagnóstico (90P).")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})

            path_sd = _guardar_temp_file(file_sd)
            try:
                res = extraer_tiras_diagnostico(path_sd, user=request.user)
            finally:
                if os.path.exists(path_sd): os.remove(path_sd)

            if res.get('error'):
                messages.warning(request, f"Advertencia OMR: {res['error']}")

            request.session['clave_omr_data'] = {
                'tipo': 'diagnostico',
                'sd': res['sd'],
                'error': res.get('error'),
            }
            return redirect('simulacros:revisar_clave_omr')

        messages.error(request, "Tipo de simulacro no válido.")
        return render(request, self.template_name)


class RevisarClaveOMRView(LoginRequiredMixin, View):
    """Paso 2: Revisar y corregir individualmente cada opción detectada por el OMR."""
    template_name = 'simulacros/crear_omr_revisar.html'

    def get(self, request):
        data = request.session.get('clave_omr_data')
        if not data:
            messages.error(request, "No hay escaneos pendientes de revisión. Por favor sube la hoja modelo.")
            return redirect('simulacros:crear_con_omr')

        context = {
            'data': data,
            'tipo': data['tipo'],
            'longitudes': LONGITUDES_ESPERADAS,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        data = request.session.get('clave_omr_data')
        if not data:
            messages.error(request, "Sesión expirada. Por favor sube la hoja modelo nuevamente.")
            return redirect('simulacros:crear_con_omr')

        tipo = data['tipo']

        if tipo == 'completo':
            s1_tiras = []
            for tira in data['s1']:
                etq = tira['etiqueta']
                val = request.POST.get(f"s1_{etq}", tira['secuencia']).upper().strip()
                s1_tiras.append(val)

            s2_tiras = []
            for tira in data['s2']:
                etq = tira['etiqueta']
                val = request.POST.get(f"s2_{etq}", tira['secuencia']).upper().strip()
                s2_tiras.append(val)

            seq_s1 = ''.join(s1_tiras)
            seq_s2 = ''.join(s2_tiras)

            if len(seq_s1) != 120:
                messages.error(request, f"La Sesión 1 debe tener exactamente 120 respuestas. Actualmente tiene {len(seq_s1)}.")
                return render(request, self.template_name, {'data': data, 'tipo': tipo, 'longitudes': LONGITUDES_ESPERADAS})

            if len(seq_s2) != 134:
                messages.error(request, f"La Sesión 2 debe tener exactamente 134 respuestas. Actualmente tiene {len(seq_s2)}.")
                return render(request, self.template_name, {'data': data, 'tipo': tipo, 'longitudes': LONGITUDES_ESPERADAS})

            request.session['clave_omr_final'] = {
                'tipo': 'completo',
                'soluciones_s1': seq_s1,
                'soluciones_s2': seq_s2,
            }
            return redirect('simulacros:guardar_simulacro_omr')

        elif tipo == 'diagnostico':
            sd_tiras = []
            for tira in data['sd']:
                etq = tira['etiqueta']
                val = request.POST.get(f"sd_{etq}", tira['secuencia']).upper().strip()
                sd_tiras.append(val)

            seq_sd = ''.join(sd_tiras)
            if len(seq_sd) != 90:
                messages.error(request, f"El Simulacro Diagnóstico debe tener exactamente 90 respuestas. Actualmente tiene {len(seq_sd)}.")
                return render(request, self.template_name, {'data': data, 'tipo': tipo, 'longitudes': LONGITUDES_ESPERADAS})

            request.session['clave_omr_final'] = {
                'tipo': 'diagnostico',
                'soluciones': seq_sd,
            }
            return redirect('simulacros:guardar_simulacro_omr')

        return redirect('simulacros:crear_con_omr')


class GuardarSimulacroOMRView(LoginRequiredMixin, View):
    """Paso 3: Formulario final para guardar el objeto con sus demás parámetros."""
    template_name = 'simulacros/crear_omr_guardar.html'

    def get(self, request):
        final_data = request.session.get('clave_omr_final')
        if not final_data:
            messages.error(request, "No hay secuencias verificadas para guardar.")
            return redirect('simulacros:crear_con_omr')

        context = {
            'tipo': final_data['tipo'],
            'soluciones_s1': final_data.get('soluciones_s1', ''),
            'soluciones_s2': final_data.get('soluciones_s2', ''),
            'soluciones': final_data.get('soluciones', ''),
            'default_componentes_s1': _DEFAULT_COMPONENTES_S1,
            'default_componentes_s2': _DEFAULT_COMPONENTES_S2,
            'default_componentes_sd': _DEFAULT_COMPONENTES_SD,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        final_data = request.session.get('clave_omr_final')
        if not final_data:
            messages.error(request, "Sesión expirada. Por favor repite el proceso.")
            return redirect('simulacros:crear_con_omr')

        tipo = final_data['tipo']
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            messages.error(request, "El nombre del simulacro es obligatorio.")
            return self.get(request)

        try:
            umbral = int(request.POST.get('umbral', 200))
            umbral_1 = int(request.POST.get('umbral_1', 140))
            objetivo_1 = int(request.POST.get('objetivo_1', 245))
            umbral_2 = int(request.POST.get('umbral_2', 240))
            objetivo_2 = int(request.POST.get('objetivo_2', 280))
            objetivo_3 = int(request.POST.get('objetivo_3', 310))
            boost_min = int(request.POST.get('boost_min', 6))
            boost_max = int(request.POST.get('boost_max', 12))
        except (ValueError, TypeError):
            messages.error(request, "Los valores numéricos de umbrales y objetivos deben ser válidos.")
            return self.get(request)

        if tipo == 'completo':
            soluciones_s1 = request.POST.get('soluciones_s1', final_data.get('soluciones_s1', '')).strip().upper()
            soluciones_s2 = request.POST.get('soluciones_s2', final_data.get('soluciones_s2', '')).strip().upper()

            simulacro = Simulacro(
                nombre=nombre,
                soluciones_s1=soluciones_s1,
                soluciones_s2=soluciones_s2,
                umbral=umbral,
                umbral_1=umbral_1,
                objetivo_1=objetivo_1,
                umbral_2=umbral_2,
                objetivo_2=objetivo_2,
                objetivo_3=objetivo_3,
                boost_min=boost_min,
                boost_max=boost_max,
                componentes_s1=_DEFAULT_COMPONENTES_S1,
                componentes_s2=_DEFAULT_COMPONENTES_S2,
                puntos_corte_s1={"cortes": [30, 60, 90]},
                puntos_corte_s2={"cortes": [48, 79, 96]},
            )
            simulacro.full_clean()
            simulacro.save()

            # Limpiar datos de sesión
            request.session.pop('clave_omr_data', None)
            request.session.pop('clave_omr_final', None)

            messages.success(request, f"¡Simulacro presencial '{simulacro.nombre}' creado exitosamente con sus respuestas OMR!")
            return redirect('simulacros:resultados_simulacros')

        elif tipo == 'diagnostico':
            soluciones = request.POST.get('soluciones', final_data.get('soluciones', '')).strip().upper()

            simulacro_diag = SimulacroDiagnostico(
                nombre=nombre,
                soluciones=soluciones,
                umbral=umbral,
                umbral_1=umbral_1,
                objetivo_1=objetivo_1,
                umbral_2=umbral_2,
                objetivo_2=objetivo_2,
                objetivo_3=objetivo_3,
                boost_min=boost_min,
                boost_max=boost_max,
                componentes=_DEFAULT_COMPONENTES_SD,
                puntos_corte={"cortes": [18, 36, 54, 72]},
            )
            simulacro_diag.full_clean()
            simulacro_diag.save()

            request.session.pop('clave_omr_data', None)
            request.session.pop('clave_omr_final', None)

            messages.success(request, f"¡Simulacro Diagnóstico '{simulacro_diag.nombre}' creado exitosamente con sus respuestas OMR!")
            return redirect('simulacros:resultados_diagnosticos')

        return redirect('simulacros:crear_con_omr')
