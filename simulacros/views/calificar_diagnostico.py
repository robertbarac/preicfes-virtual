# views/calificar_diagnostico.py

import os
import tempfile
import uuid
import shutil

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

from academico.models import Grupo, Alumno
from ..models import SimulacroDiagnostico, ResultadoSimulacroDiagnostico
from ..procesar_simulacro import extraer_preguntas_con_recortes, LONGITUDES_ESPERADAS
from ..calculos import calificar, calcular_puntaje_icfes, modificar_puntajes


class GrupoCalificarDiagnosticoView(LoginRequiredMixin, View):
    """
    Vista para subir y procesar imágenes del Simulacro Diagnóstico (90 preguntas, 1 sola hoja por alumno).
    """

    def get(self, request, grupo_id):
        grupo = get_object_or_404(Grupo, id=grupo_id)
        alumnos = Alumno.objects.filter(grupo_actual=grupo).order_by('primer_apellido', 'segundo_apellido')
        simulacros = SimulacroDiagnostico.objects.all()

        context = {
            'grupo': grupo,
            'alumnos': alumnos,
            'simulacros': simulacros,
        }
        return render(request, 'simulacros/calificar_diagnostico_grupo.html', context)

    def post(self, request, grupo_id):
        grupo = get_object_or_404(Grupo, id=grupo_id)

        simulacro_id      = request.POST.get('simulacro')
        fecha_realizacion = request.POST.get('fecha_realizacion')
        alumnos_ids       = request.POST.getlist('alumnos_seleccionados')
        archivos          = request.FILES.getlist('imagenes')

        if not simulacro_id or not fecha_realizacion or not alumnos_ids or not archivos:
            messages.error(request, "Faltan datos requeridos para procesar.")
            return redirect('simulacros:grupo_calificar_diagnostico', grupo_id=grupo.id)

        simulacro = get_object_or_404(SimulacroDiagnostico, id=simulacro_id)

        # Para el diagnóstico es EXACTAMENTE 1 imagen por alumno
        if len(archivos) != len(alumnos_ids):
            messages.error(
                request, 
                f"La cantidad de imágenes ({len(archivos)}) no coincide con la cantidad de alumnos ({len(alumnos_ids)}). Debe ser 1 imagen por alumno."
            )
            return redirect('simulacros:grupo_calificar_diagnostico', grupo_id=grupo.id)

        archivos_ordenados = sorted(archivos, key=lambda x: x.name)
        alumnos_map = {str(a.id): a for a in Alumno.objects.filter(id__in=alumnos_ids)}
        alumnos_seleccionados = [alumnos_map[aid] for aid in alumnos_ids if aid in alumnos_map]

        token = uuid.uuid4().hex
        batch = {
            'token':        token,
            'simulacro_id': simulacro_id,
            'grupo_id':     grupo_id,
            'fecha':        fecha_realizacion,
            'alumnos':      [],
        }

        with tempfile.TemporaryDirectory() as tmpdirname:
            for idx, alumno in enumerate(alumnos_seleccionados):
                file_sd = archivos_ordenados[idx]
                path_sd = os.path.join(tmpdirname, file_sd.name)

                with open(path_sd, 'wb+') as dest:
                    for chunk in file_sd.chunks():
                        dest.write(chunk)

                alumno_err = None
                p_sd = []

                try:
                    p_sd = extraer_preguntas_con_recortes(path_sd, 'SD', token, user=request.user, prefix=f"a{alumno.id}_")
                except Exception as e:
                    alumno_err = f"SD: {e}"

                dudas_sd = sum(1 for p in p_sd if p.get('es_dudosa'))

                batch['alumnos'].append({
                    'id':           alumno.id,
                    'nombre':       f"{alumno.primer_apellido} {alumno.segundo_apellido} {alumno.nombres}".strip(),
                    'preguntas_sd': p_sd,
                    'dudas_count':  dudas_sd,
                    'error':        alumno_err,
                })

        request.session['simulacro_diagnostico_batch'] = batch
        return redirect('simulacros:revisar_diagnostico')


class RevisarDiagnosticoView(LoginRequiredMixin, View):
    """
    Vista intermedia para revisar/corregir preguntas OMR recortadas del Simulacro Diagnóstico
    antes de calificar.
    """

    def get(self, request):
        batch = request.session.get('simulacro_diagnostico_batch')
        if not batch:
            messages.error(request, "No hay datos de simulacro diagnóstico pendientes de revisión.")
            return redirect('simulacros:resultados_simulacros')

        simulacro = get_object_or_404(SimulacroDiagnostico, id=batch['simulacro_id'])
        grupo = get_object_or_404(Grupo, id=batch['grupo_id'])

        total_dudosas = sum(a.get('dudas_count', 0) for a in batch['alumnos'])
        total_errores = sum(1 for a in batch['alumnos'] if a.get('error'))

        context = {
            'batch':         batch,
            'simulacro':     simulacro,
            'grupo':         grupo,
            'alumnos':       batch['alumnos'],
            'total_alumnos': len(batch['alumnos']),
            'total_dudosas': total_dudosas,
            'total_errores': total_errores,
        }
        return render(request, 'simulacros/revisar_diagnostico.html', context)

    def post(self, request):
        batch = request.session.get('simulacro_diagnostico_batch')
        if not batch:
            messages.error(request, "Sesión expirada. Por favor vuelve a subir las imágenes.")
            return redirect('simulacros:resultados_simulacros')

        simulacro = get_object_or_404(SimulacroDiagnostico, id=batch['simulacro_id'])
        fecha_realizacion = batch['fecha']

        componentes = simulacro.get_componentes()
        c_sd = simulacro.puntos_corte
        cortes = c_sd if isinstance(c_sd, list) else c_sd.get('cortes', [18, 36, 54, 72])

        errores_calificacion = []

        for alumno_data in batch['alumnos']:
            alumno_id = alumno_data['id']
            alumno    = get_object_or_404(Alumno, id=alumno_id)

            # Reconstruir SD (90 preguntas)
            sd_list = []
            for k in range(1, 91):
                val = request.POST.get(f"sd_{alumno_id}_q_{k}")
                if not val or val not in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'Z'):
                    p_orig = alumno_data.get('preguntas_sd', [])
                    val = p_orig[k - 1]['opcion'] if (k - 1 < len(p_orig)) else 'Z'
                sd_list.append(val)
            resp_sd = ''.join(sd_list)

            try:
                comp_results = calificar(resp_sd, simulacro.soluciones, cortes, componentes)
                puntajes     = calcular_puntaje_icfes(comp_results)
                puntajes_modificados = modificar_puntajes(puntajes, simulacro)

                ResultadoSimulacroDiagnostico.objects.update_or_create(
                    alumno=alumno,
                    simulacro=simulacro,
                    defaults={
                        'respuestas':          resp_sd,
                        'puntaje_global':      puntajes['global'],
                        'puntaje_matematicas': puntajes.get('matematicas', 0),
                        'puntaje_lectura':     puntajes.get('lectura', 0),
                        'puntaje_sociales':    puntajes.get('sociales', 0),
                        'puntaje_naturales':   puntajes.get('naturales', 0),
                        'puntaje_ingles':      puntajes.get('ingles', 0),
                        'puntaje_global_modificado':      puntajes_modificados['global'],
                        'puntaje_matematicas_modificado': puntajes_modificados.get('matematicas', 0),
                        'puntaje_lectura_modificado':     puntajes_modificados.get('lectura', 0),
                        'puntaje_sociales_modificado':    puntajes_modificados.get('sociales', 0),
                        'puntaje_naturales_modificado':   puntajes_modificados.get('naturales', 0),
                        'puntaje_ingles_modificado':      puntajes_modificados.get('ingles', 0),
                        'fecha_realizacion': fecha_realizacion,
                        'registrador':       request.user,
                    }
                )
            except Exception as e:
                errores_calificacion.append(f"{alumno}: {e}")

        # Limpiar imágenes temporales de recorte del lote
        if batch.get('token'):
            token_dir = os.path.join(settings.MEDIA_ROOT, 'temp_omr_crops', batch['token'])
            if os.path.exists(token_dir):
                shutil.rmtree(token_dir, ignore_errors=True)

        del request.session['simulacro_diagnostico_batch']

        for err in errores_calificacion:
            messages.error(request, f"Error calificando: {err}")

        messages.success(request, "Simulacros Diagnósticos calificados exitosamente.")
        grupo_id = batch['grupo_id']
        return redirect(
            f"{reverse('simulacros:resultados_diagnosticos')}"
            f"?grupo={grupo_id}"
            f"&fecha_inicio={fecha_realizacion}&fecha_fin={fecha_realizacion}"
        )
