import os
import shutil
import uuid
import tempfile
import cv2
import numpy as np

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.urls import reverse

from ..models import (
    Simulacro, SimulacroDiagnostico,
    _DEFAULT_COMPONENTES_S1, _DEFAULT_COMPONENTES_S2, _DEFAULT_COMPONENTES_SD
)
from ..procesar_simulacro import (
    normalizar_hoja, hacer_tiras, encontrar_circulos_en_tira, evaluar_tira,
    LONGITUDES_ESPERADAS, ETIQUETAS_S1, ETIQUETAS_S2, ETIQUETAS_SD,
    extraer_preguntas_con_recortes as _extraer_preguntas_con_recortes
)


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe el acceso exclusivamente a superusuarios."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("Solo los superusuarios pueden acceder a la creación de simulacros por OMR.")


def _guardar_temp_file(uploaded_file):
    """Guarda un archivo subido en el directorio temporal y retorna su ruta."""
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in uploaded_file.chunks():
        tmp.write(chunk)
    tmp.close()
    return tmp.name


class CrearSimulacroOMRView(SuperuserRequiredMixin, View):
    """Paso 1: Subir imagen(es) de la hoja modelo para escanear con OMR."""
    template_name = 'simulacros/crear_omr_subir.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        tipo = request.POST.get('tipo', 'completo')
        token = uuid.uuid4().hex

        if tipo == 'completo':
            file_s1 = request.FILES.get('imagen_s1')
            file_s2 = request.FILES.get('imagen_s2')

            if not file_s1 or not file_s2:
                messages.error(request, "Para el simulacro completo debes subir ambas hojas modelo: Sesión 1 y Sesión 2.")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})

            path_s1 = _guardar_temp_file(file_s1)
            path_s2 = _guardar_temp_file(file_s2)

            try:
                preguntas_s1 = _extraer_preguntas_con_recortes(path_s1, 'S1', token, user=request.user)
                preguntas_s2 = _extraer_preguntas_con_recortes(path_s2, 'S2', token, user=request.user)
            except Exception as e:
                messages.error(request, f"Error al procesar las hojas con OMR: {e}")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})
            finally:
                if os.path.exists(path_s1): os.remove(path_s1)
                if os.path.exists(path_s2): os.remove(path_s2)

            request.session['clave_omr_data'] = {
                'token': token,
                'tipo': 'completo',
                'preguntas_s1': preguntas_s1,
                'preguntas_s2': preguntas_s2,
            }
            return redirect('simulacros:revisar_clave_omr')

        elif tipo == 'diagnostico':
            file_sd = request.FILES.get('imagen_sd')
            if not file_sd:
                messages.error(request, "Debes subir la hoja modelo del Simulacro Diagnóstico (90 preguntas).")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})

            path_sd = _guardar_temp_file(file_sd)
            try:
                preguntas_sd = _extraer_preguntas_con_recortes(path_sd, 'SD', token, user=request.user)
            except Exception as e:
                messages.error(request, f"Error al procesar la hoja de diagnóstico con OMR: {e}")
                return render(request, self.template_name, {'tipo_seleccionado': tipo})
            finally:
                if os.path.exists(path_sd): os.remove(path_sd)

            request.session['clave_omr_data'] = {
                'token': token,
                'tipo': 'diagnostico',
                'preguntas_sd': preguntas_sd,
            }
            return redirect('simulacros:revisar_clave_omr')

        messages.error(request, "Tipo de simulacro no válido.")
        return render(request, self.template_name)


class RevisarClaveOMRView(SuperuserRequiredMixin, View):
    """Paso 2: Revisar y corregir pregunta por pregunta con su imagen recortada y selector de opciones."""
    template_name = 'simulacros/crear_omr_revisar.html'

    def get(self, request):
        data = request.session.get('clave_omr_data')
        if not data:
            messages.error(request, "No hay escaneos pendientes de revisión. Por favor sube la hoja modelo.")
            return redirect('simulacros:crear_con_omr')

        tipo = data['tipo']
        context = {
            'tipo': tipo,
            'token': data.get('token'),
        }

        if tipo == 'completo':
            preguntas_s1 = data.get('preguntas_s1', [])
            preguntas_s2 = data.get('preguntas_s2', [])
            dudosas_s1 = sum(1 for p in preguntas_s1 if p.get('es_dudosa'))
            dudosas_s2 = sum(1 for p in preguntas_s2 if p.get('es_dudosa'))
            context.update({
                'preguntas_s1': preguntas_s1,
                'preguntas_s2': preguntas_s2,
                'total_preguntas': len(preguntas_s1) + len(preguntas_s2),
                'total_dudosas': dudosas_s1 + dudosas_s2,
                'dudosas_s1': dudosas_s1,
                'dudosas_s2': dudosas_s2,
            })
        else:
            preguntas_sd = data.get('preguntas_sd', [])
            dudosas_sd = sum(1 for p in preguntas_sd if p.get('es_dudosa'))
            context.update({
                'preguntas_sd': preguntas_sd,
                'total_preguntas': len(preguntas_sd),
                'total_dudosas': dudosas_sd,
            })

        return render(request, self.template_name, context)

    def post(self, request):
        data = request.session.get('clave_omr_data')
        if not data:
            messages.error(request, "Sesión expirada. Por favor sube la hoja modelo nuevamente.")
            return redirect('simulacros:crear_con_omr')

        tipo = data['tipo']

        if tipo == 'completo':
            s1_vals = [request.POST.get(f"s1_q_{i}", 'Z').upper().strip() for i in range(1, 121)]
            s2_vals = [request.POST.get(f"s2_q_{i}", 'Z').upper().strip() for i in range(1, 135)]

            # Normalizar caracteres no reconocidos
            s1_vals = [v if v in ('A', 'B', 'C', 'D') else 'Z' for v in s1_vals]
            s2_vals = [v if v in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H') else 'Z' for v in s2_vals]

            seq_s1 = ''.join(s1_vals)
            seq_s2 = ''.join(s2_vals)

            if len(seq_s1) != 120 or len(seq_s2) != 134:
                messages.error(request, "Las respuestas no tienen la longitud esperada (120 en S1 y 134 en S2).")
                return self.get(request)

            request.session['clave_omr_final'] = {
                'token': data.get('token'),
                'tipo': 'completo',
                'soluciones_s1': seq_s1,
                'soluciones_s2': seq_s2,
            }
            return redirect('simulacros:guardar_simulacro_omr')

        elif tipo == 'diagnostico':
            sd_vals = [request.POST.get(f"sd_q_{i}", 'Z').upper().strip() for i in range(1, 91)]
            sd_vals = [v if v in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H') else 'Z' for v in sd_vals]

            seq_sd = ''.join(sd_vals)
            if len(seq_sd) != 90:
                messages.error(request, "El Simulacro Diagnóstico debe tener exactamente 90 respuestas.")
                return self.get(request)

            request.session['clave_omr_final'] = {
                'token': data.get('token'),
                'tipo': 'diagnostico',
                'soluciones': seq_sd,
            }
            return redirect('simulacros:guardar_simulacro_omr')

        return redirect('simulacros:crear_con_omr')


class GuardarSimulacroOMRView(SuperuserRequiredMixin, View):
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
        token = final_data.get('token')

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

        def _cleanup_crops():
            if token:
                crops_dir = os.path.join(settings.MEDIA_ROOT, 'temp_omr_crops', token)
                if os.path.exists(crops_dir):
                    try:
                        shutil.rmtree(crops_dir)
                    except Exception:
                        pass

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

            _cleanup_crops()
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

            _cleanup_crops()
            request.session.pop('clave_omr_data', None)
            request.session.pop('clave_omr_final', None)

            messages.success(request, f"¡Simulacro Diagnóstico '{simulacro_diag.nombre}' creado exitosamente con sus respuestas OMR!")
            return redirect('simulacros:resultados_diagnosticos')

        return redirect('simulacros:crear_con_omr')
