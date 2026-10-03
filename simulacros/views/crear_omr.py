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
    LONGITUDES_ESPERADAS, ETIQUETAS_S1, ETIQUETAS_S2, ETIQUETAS_SD
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


def _extraer_preguntas_con_recortes(path_imagen, modo, token, user=None):
    """
    Procesa una hoja modelo escaneada, extrae las tiras y recorta individualmente
    cada pregunta (fila de burbujas), guardando el recorte como imagen JPEG.
    
    Retorna:
        list of dicts: [
            {
                'num': 1,
                'opcion': 'A',  # detectada por OMR o 'Z' si vacía/dudosa
                'n_opciones': 4, # 4 u 8
                'opciones_disponibles': ['A', 'B', 'C', 'D'],
                'img_url': '/media/temp_omr_crops/<token>/s1_q1.jpg',
                'materia': 'Matemáticas',
                'columna': 'C1',
                'es_dudosa': False,
            },
            ...
        ]
    """
    crops_dir = os.path.join(settings.MEDIA_ROOT, 'temp_omr_crops', token)
    os.makedirs(crops_dir, exist_ok=True)

    img = cv2.imread(path_imagen)
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {path_imagen}")
    
    img = normalizar_hoja(img)
    tiras = hacer_tiras(img, modo, user=user)

    # Nombres de materia según columna y modo
    MATERIAS_S1 = {
        'C1': 'Matemáticas (1-30)',
        'C2': 'Lectura Crítica (31-60)',
        'C3': 'Sociales y Ciudadanas (61-90)',
        'C4': 'Ciencias Naturales (91-120)',
    }
    MATERIAS_S2 = {
        'C1': 'Sociales y Ciudadanas 2 (1-45)',
        'C2a': 'Matemáticas 2 (46-79)',
        'C2b': 'Ciencias Naturales 2 (80-89)',
        'C3': 'Inglés (90-134)',
    }
    MATERIAS_SD = {
        'C1': 'Matemáticas / Lectura (1-30)',
        'C2': 'Lectura / Sociales / Naturales (31-60)',
        'C3a': 'Ciencias Naturales (61-72)',
        'C3b': 'Inglés (73-90)',
    }

    if modo == 'S1':
        materias_map = MATERIAS_S1
    elif modo == 'S2':
        materias_map = MATERIAS_S2
    else:
        materias_map = MATERIAS_SD

    preguntas = []
    q_global_num = 1

    for i, (tira_img, n_opciones, _etq) in enumerate(tiras):
        if modo == 'S1':
            etiqueta = ETIQUETAS_S1[i]
        elif modo == 'S2':
            etiqueta = ETIQUETAS_S2[i]
        else:
            etiqueta = ETIQUETAS_SD[i]

        esperado = LONGITUDES_ESPERADAS[modo][etiqueta]
        materia_label = materias_map.get(etiqueta, f"Columna {etiqueta}")

        # OMR sobre la tira
        imgThresh, circulos, _ = encontrar_circulos_en_tira(tira_img, n_opciones)
        respuestas = evaluar_tira(circulos, imgThresh, n_opciones)

        # Agrupar círculos en filas para extraer coordenadas verticales
        burbujas = []
        for c in circulos:
            x, y, w, h = cv2.boundingRect(c)
            burbujas.append({'x': x, 'y': y, 'w': w, 'h': h, 'cY': y + h // 2})

        filas = []
        if burbujas:
            burbujas = sorted(burbujas, key=lambda b: b['cY'])
            tol_y = burbujas[0]['h'] * 0.70
            fila_cur = [burbujas[0]]
            for b in burbujas[1:]:
                if abs(b['cY'] - fila_cur[-1]['cY']) < tol_y:
                    fila_cur.append(b)
                else:
                    filas.append(fila_cur)
                    fila_cur = [b]
            filas.append(fila_cur)

        H_tira, W_tira = tira_img.shape[:2]
        row_height = H_tira / float(esperado) if esperado > 0 else 30

        # Para cada una de las preguntas de esta tira
        for k in range(esperado):
            opcion = respuestas[k] if k < len(respuestas) else 'Z'
            if opcion not in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
                opcion = 'Z'

            # Determinar coordenadas de recorte vertical
            if len(filas) == esperado:
                f = filas[k]
                min_y = min(b['y'] for b in f)
                max_y = max(b['y'] + b['h'] for b in f)
                pad = 6
                y1 = max(0, min_y - pad)
                y2 = min(H_tira, max_y + pad)
            else:
                # Sincronización por centroide o rejilla proporcional
                target_cy = (k + 0.5) * row_height
                matching_f = None
                for f in filas:
                    c_y = sum(b['cY'] for b in f) / float(len(f))
                    if abs(c_y - target_cy) < row_height * 0.45:
                        matching_f = f
                        break
                if matching_f:
                    min_y = min(b['y'] for b in matching_f)
                    max_y = max(b['y'] + b['h'] for b in matching_f)
                    pad = 6
                    y1 = max(0, min_y - pad)
                    y2 = min(H_tira, max_y + pad)
                else:
                    y1 = max(0, int(k * row_height))
                    y2 = min(H_tira, int((k + 1) * row_height))

            # Extraer recorte
            crop_img = tira_img[y1:y2, 0:W_tira]
            if crop_img.size == 0 or crop_img.shape[0] < 5:
                y1 = max(0, int(k * row_height))
                y2 = min(H_tira, int((k + 1) * row_height))
                crop_img = tira_img[y1:y2, 0:W_tira]

            # Guardar recorte
            crop_name = f"{modo.lower()}_{etiqueta.lower()}_q{q_global_num}.jpg"
            crop_path = os.path.join(crops_dir, crop_name)
            cv2.imwrite(crop_path, crop_img)

            img_url = f"{settings.MEDIA_URL}temp_omr_crops/{token}/{crop_name}"
            opciones_disp = ['A', 'B', 'C', 'D'] if n_opciones == 4 else ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

            preguntas.append({
                'num': q_global_num,
                'opcion': opcion,
                'n_opciones': n_opciones,
                'opciones_disponibles': opciones_disp,
                'img_url': img_url,
                'materia': materia_label,
                'columna': etiqueta,
                'es_dudosa': (opcion == 'Z'),
            })

            q_global_num += 1

    return preguntas


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
