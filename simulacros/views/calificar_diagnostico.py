# views/calificar_diagnostico.py

import os
import tempfile

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse

from academico.models import Grupo, Alumno
from ..models import SimulacroDiagnostico, ResultadoSimulacroDiagnostico
from ..procesar_simulacro import extraer_tiras_diagnostico, LONGITUDES_ESPERADAS
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

        batch = {
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

                resultado = extraer_tiras_diagnostico(path_sd, user=request.user)

                batch['alumnos'].append({
                    'id':     alumno.id,
                    'nombre': f"{alumno.primer_apellido} {alumno.segundo_apellido} {alumno.nombres}".strip(),
                    'sd':     resultado['sd'],
                    'error':  resultado.get('error'),
                })

        request.session['simulacro_diagnostico_batch'] = batch
        return redirect('simulacros:revisar_diagnostico')


class RevisarDiagnosticoView(LoginRequiredMixin, View):
    """
    Vista intermedia para revisar/corregir secuencias OMR del Simulacro Diagnóstico antes de guardar.
    """

    def get(self, request):
        batch = request.session.get('simulacro_diagnostico_batch')
        if not batch:
            messages.error(request, "No hay datos de simulacro diagnóstico pendientes de revisión.")
            return redirect('simulacros:resultados_simulacros')

        simulacro = get_object_or_404(SimulacroDiagnostico, id=batch['simulacro_id'])

        total_errores = 0
        for alumno in batch['alumnos']:
            for tira in alumno['sd']:
                if not tira['ok']:
                    total_errores += 1
            if alumno.get('error'):
                total_errores += 1

        context = {
            'batch':         batch,
            'simulacro':     simulacro,
            'total_errores': total_errores,
            'longitudes':    LONGITUDES_ESPERADAS['SD'],
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

            # Leer secuencias corregidas desde el formulario
            sd_tiras = [
                request.POST.get(f"sd_{alumno_id}_{tira['etiqueta']}", tira['secuencia'])
                for tira in alumno_data['sd']
            ]

            resp_sd = ''.join(sd_tiras)

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
