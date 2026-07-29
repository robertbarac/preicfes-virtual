# views/calificar.py

import os
import tempfile

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse

from academico.models import Grupo, Alumno
from ..models import Simulacro, ResultadoSimulacro
from ..procesar_simulacro import extraer_tiras_individuales, LONGITUDES_ESPERADAS
from ..calculos import calificar, calcular_puntaje_icfes, modificar_puntajes


class GrupoCalificarSimulacroView(LoginRequiredMixin, View):
    def get(self, request, grupo_id):
        grupo = get_object_or_404(Grupo, id=grupo_id)
        alumnos = Alumno.objects.filter(grupo_actual=grupo).order_by('primer_apellido', 'segundo_apellido')
        simulacros = Simulacro.objects.all()

        context = {
            'grupo': grupo,
            'alumnos': alumnos,
            'simulacros': simulacros,
        }
        return render(request, 'simulacros/calificar_grupo.html', context)

    def post(self, request, grupo_id):
        grupo = get_object_or_404(Grupo, id=grupo_id)

        simulacro_id      = request.POST.get('simulacro')
        fecha_realizacion = request.POST.get('fecha_realizacion')
        alumnos_ids       = request.POST.getlist('alumnos_seleccionados')
        archivos          = request.FILES.getlist('imagenes')

        if not simulacro_id or not fecha_realizacion or not alumnos_ids or not archivos:
            messages.error(request, "Faltan datos requeridos para procesar.")
            return redirect('simulacros:grupo_calificar_simulacro', grupo_id=grupo.id)

        simulacro = get_object_or_404(Simulacro, id=simulacro_id)

        if len(archivos) != len(alumnos_ids) * 2:
            messages.error(request, f"La cantidad de imágenes ({len(archivos)}) no coincide con el doble de alumnos ({len(alumnos_ids) * 2}).")
            return redirect('simulacros:grupo_calificar_simulacro', grupo_id=grupo.id)

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
                file_s1 = archivos_ordenados[idx * 2]
                file_s2 = archivos_ordenados[idx * 2 + 1]

                path_s1 = os.path.join(tmpdirname, file_s1.name)
                path_s2 = os.path.join(tmpdirname, file_s2.name)

                with open(path_s1, 'wb+') as dest:
                    for chunk in file_s1.chunks():
                        dest.write(chunk)
                with open(path_s2, 'wb+') as dest:
                    for chunk in file_s2.chunks():
                        dest.write(chunk)

                resultado = extraer_tiras_individuales(path_s1, path_s2, user=request.user)

                batch['alumnos'].append({
                    'id':     alumno.id,
                    'nombre': f"{alumno.primer_apellido} {alumno.segundo_apellido} {alumno.nombres}".strip(),
                    's1':     resultado['s1'],
                    's2':     resultado['s2'],
                    'error':  resultado.get('error'),
                })

        request.session['simulacro_batch'] = batch
        return redirect('simulacros:revisar_simulacro')


class RevisarSimulacroView(LoginRequiredMixin, View):
    """
    Página intermedia de revisión/corrección de secuencias OMR antes de calificar.
    """

    def get(self, request):
        batch = request.session.get('simulacro_batch')
        if not batch:
            messages.error(request, "No hay datos de simulacro pendientes de revisión.")
            return redirect('simulacros:resultados_simulacros')

        simulacro = get_object_or_404(Simulacro, id=batch['simulacro_id'])

        total_errores = 0
        for alumno in batch['alumnos']:
            for tira in alumno['s1'] + alumno['s2']:
                if not tira['ok']:
                    total_errores += 1
            if alumno.get('error'):
                total_errores += 1

        context = {
            'batch':         batch,
            'simulacro':     simulacro,
            'total_errores': total_errores,
            'longitudes':    LONGITUDES_ESPERADAS,
        }
        return render(request, 'simulacros/revisar_simulacro.html', context)

    def post(self, request):
        batch = request.session.get('simulacro_batch')
        if not batch:
            messages.error(request, "Sesión expirada. Por favor vuelve a subir las imágenes.")
            return redirect('simulacros:resultados_simulacros')

        simulacro = get_object_or_404(Simulacro, id=batch['simulacro_id'])
        fecha_realizacion = batch['fecha']

        componentes_s1 = simulacro.get_componentes_s1()
        componentes_s2 = simulacro.get_componentes_s2()

        c_s1 = simulacro.puntos_corte_s1
        cortes_s1 = c_s1 if isinstance(c_s1, list) else c_s1.get('cortes', [])
        c_s2 = simulacro.puntos_corte_s2
        cortes_s2 = c_s2 if isinstance(c_s2, list) else c_s2.get('cortes', [])

        errores_calificacion = []

        for alumno_data in batch['alumnos']:
            alumno_id = alumno_data['id']
            alumno    = get_object_or_404(Alumno, id=alumno_id)

            # Leer secuencias corregidas desde el formulario
            s1_tiras = [
                request.POST.get(f"s1_{alumno_id}_{tira['etiqueta']}", tira['secuencia'])
                for tira in alumno_data['s1']
            ]
            s2_tiras = [
                request.POST.get(f"s2_{alumno_id}_{tira['etiqueta']}", tira['secuencia'])
                for tira in alumno_data['s2']
            ]

            resp_s1 = ''.join(s1_tiras)
            resp_s2 = ''.join(s2_tiras)

            try:
                comp_s1 = calificar(resp_s1, simulacro.soluciones_s1, cortes_s1, componentes_s1)
                comp_s2 = calificar(resp_s2, simulacro.soluciones_s2, cortes_s2, componentes_s2)

                consolidados = {}
                for comp in set(componentes_s1 + componentes_s2):
                    consolidados[comp] = {'buenas': 0, 'totales': 0}
                    if comp in comp_s1:
                        consolidados[comp]['buenas']  += comp_s1[comp]['buenas']
                        consolidados[comp]['totales'] += comp_s1[comp]['totales']
                    if comp in comp_s2:
                        consolidados[comp]['buenas']  += comp_s2[comp]['buenas']
                        consolidados[comp]['totales'] += comp_s2[comp]['totales']

                puntajes          = calcular_puntaje_icfes(consolidados)
                # SE PASA EL SIMULACRO COMPLETO PARA SOPORTAR LOS PARÁMETROS CONFIGURABLES DESDE EL ADMIN
                puntajes_modificados = modificar_puntajes(puntajes, simulacro)

                ResultadoSimulacro.objects.update_or_create(
                    alumno=alumno,
                    simulacro=simulacro,
                    defaults={
                        'respuestas_s1': resp_s1,
                        'respuestas_s2': resp_s2,
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

        del request.session['simulacro_batch']

        for err in errores_calificacion:
            messages.error(request, f"Error calificando: {err}")

        messages.success(request, "Simulacros calificados exitosamente.")
        grupo_id = batch['grupo_id']
        return redirect(
            f"{reverse('simulacros:resultados_simulacros')}"
            f"?grupo={grupo_id}&simulacro={batch['simulacro_id']}"
            f"&fecha_inicio={fecha_realizacion}&fecha_fin={fecha_realizacion}"
        )
