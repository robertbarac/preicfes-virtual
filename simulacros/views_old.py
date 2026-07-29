import os

import tempfile
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse

from academico.models import Grupo, Alumno
from ubicaciones.models import Sede
from .models import Simulacro, ResultadoSimulacro
from .procesar_simulacro import procesar_imagen
from .calculos import calificar, calcular_puntaje_icfes

# ReportLab imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage, KeepTogether
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .recomendaciones import generar_reporte_completo
from django.conf import settings

# ── Barra de desempeño relativo (Flowable personalizado) ─────────────────────
class BarraDesempeno(Flowable):
    """Barra de color rojo→naranja→amarillo→verde con triángulo marcador."""
    def __init__(self, pct, width=185, height=11):
        Flowable.__init__(self)
        self.pct = min(max(float(pct), 0), 100)
        self.bar_width = width
        self.bar_height = height

    def wrap(self, availWidth, availHeight):
        return (self.bar_width + 36, self.bar_height + 8)

    def draw(self):
        c = self.canv
        w = self.bar_width
        h = self.bar_height
        yo = 5  # espacio inferior para el triángulo
        # Segmentos de color
        segs = [
            (0,  33, colors.HexColor('#C0392B')),
            (33, 50, colors.HexColor('#E67E22')),
            (50, 67, colors.HexColor('#F1C40F')),
            (67, 100, colors.HexColor('#27AE60')),
        ]
        for s, e, col in segs:
            x1 = w * s / 100
            x2 = w * e / 100
            c.setFillColor(col)
            c.rect(x1, yo, x2 - x1, h, stroke=0, fill=1)
        # Borde
        c.setStrokeColor(colors.HexColor('#AAAAAA'))
        c.setLineWidth(0.4)
        c.rect(0, yo, w, h, stroke=1, fill=0)
        # Triángulo marcador
        mx = w * self.pct / 100
        c.setFillColor(colors.black)
        tri = 4
        p = c.beginPath()
        p.moveTo(mx, yo - 1)
        p.lineTo(mx - tri, yo - 1 - tri * 1.5)
        p.lineTo(mx + tri, yo - 1 - tri * 1.5)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        # Porcentaje a la derecha
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(colors.black)
        c.drawString(w + 4, yo + 2, f"{self.pct:.1f}%")


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
        
        simulacro_id = request.POST.get('simulacro')
        fecha_realizacion = request.POST.get('fecha_realizacion')
        alumnos_ids = request.POST.getlist('alumnos_seleccionados')
        archivos = request.FILES.getlist('imagenes')
        
        if not simulacro_id or not fecha_realizacion or not alumnos_ids or not archivos:
            messages.error(request, "Faltan datos requeridos para procesar.")
            return redirect('simulacros:grupo_calificar_simulacro', grupo_id=grupo.id)
            
        simulacro = get_object_or_404(Simulacro, id=simulacro_id)
        
        if len(archivos) != len(alumnos_ids) * 2:
            messages.error(request, f"La cantidad de imágenes ({len(archivos)}) no coincide con el doble de alumnos seleccionados ({len(alumnos_ids) * 2}).")
            return redirect('simulacros:grupo_calificar_simulacro', grupo_id=grupo.id)
            
        # Ordenar archivos por nombre (convención de nombrado del escáner)
        archivos_ordenados = sorted(archivos, key=lambda x: x.name)
        
        # Respetar el orden en que el usuario arrastró los alumnos en el formulario
        # (ese orden ya corresponde al orden del PDF escaneado)
        alumnos_map = {str(a.id): a for a in Alumno.objects.filter(id__in=alumnos_ids)}
        alumnos_seleccionados = [alumnos_map[aid] for aid in alumnos_ids if aid in alumnos_map]
        
        componentes_s1 = simulacro.get_componentes_s1()
        componentes_s2 = simulacro.get_componentes_s2()
        
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
                
                try:
                    sec_s1 = procesar_imagen(path_s1, 'S1', debug=False, user=request.user)
                    sec_s2 = procesar_imagen(path_s2, 'S2', debug=False, user=request.user)
                    
                    resp_s1 = ''.join(sec_s1)
                    resp_s2 = ''.join(sec_s2)
                    
                    # Extraer cortes
                    c_s1 = simulacro.puntos_corte_s1
                    cortes_s1 = c_s1 if isinstance(c_s1, list) else c_s1.get('cortes', [])
                    
                    c_s2 = simulacro.puntos_corte_s2
                    cortes_s2 = c_s2 if isinstance(c_s2, list) else c_s2.get('cortes', [])
                    
                    comp_s1 = calificar(resp_s1, simulacro.soluciones_s1, cortes_s1, componentes_s1)
                    comp_s2 = calificar(resp_s2, simulacro.soluciones_s2, cortes_s2, componentes_s2)
                    
                    # Consolidar
                    consolidados = {}
                    for comp in set(componentes_s1 + componentes_s2):
                        consolidados[comp] = {'buenas': 0, 'totales': 0}
                        if comp in comp_s1:
                            consolidados[comp]['buenas'] += comp_s1[comp]['buenas']
                            consolidados[comp]['totales'] += comp_s1[comp]['totales']
                        if comp in comp_s2:
                            consolidados[comp]['buenas'] += comp_s2[comp]['buenas']
                            consolidados[comp]['totales'] += comp_s2[comp]['totales']
                            
                    puntajes = calcular_puntaje_icfes(consolidados)
                    
                    # Guardar en BD
                    ResultadoSimulacro.objects.update_or_create(
                        alumno=alumno,
                        simulacro=simulacro,
                        defaults={
                            'respuestas_s1': resp_s1,
                            'respuestas_s2': resp_s2,
                            'puntaje_global': puntajes['global'],
                            'puntaje_matematicas': puntajes.get('matematicas', 0),
                            'puntaje_lectura': puntajes.get('lectura', 0),
                            'puntaje_sociales': puntajes.get('sociales', 0),
                            'puntaje_naturales': puntajes.get('naturales', 0),
                            'puntaje_ingles': puntajes.get('ingles', 0),
                            'fecha_realizacion': fecha_realizacion,
                            'registrador': request.user
                        }
                    )
                except Exception as e:
                    messages.error(request, f"Error procesando a {alumno}: {e}")
                    continue
                    
        messages.success(request, "Simulacros procesados exitosamente.")
        return redirect(f"{reverse('simulacros:resultados_simulacros')}?grupo={grupo.id}&simulacro={simulacro.id}&fecha_inicio={fecha_realizacion}&fecha_fin={fecha_realizacion}")


class PermisosResultadosMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=['CoordinadorDepartamental', 'SecretariaAcademica']).exists()

class ResultadosSimulacroListView(LoginRequiredMixin, PermisosResultadosMixin, ListView):
    model = ResultadoSimulacro
    template_name = 'simulacros/resultados_grupo.html'
    context_object_name = 'resultados'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        sede_id = self.request.GET.get('sede')
        grupo_id = self.request.GET.get('grupo')
        simulacro_id = self.request.GET.get('simulacro')
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        
        if sede_id:
            qs = qs.filter(alumno__sede_id=sede_id)
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
        context['simulacros'] = Simulacro.objects.all()
        return context

class DescargarResultadosPDFView(LoginRequiredMixin, PermisosResultadosMixin, View):
    def get(self, request):
        qs = ResultadoSimulacro.objects.all().select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('alumno__primer_apellido', 'alumno__segundo_apellido')

        sede_id = request.GET.get('sede')
        grupo_id = request.GET.get('grupo')
        simulacro_id = request.GET.get('simulacro')
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')

        if sede_id:
            qs = qs.filter(alumno__sede_id=sede_id)
        if grupo_id:
            qs = qs.filter(alumno__grupo_actual_id=grupo_id)
        if simulacro_id:
            qs = qs.filter(simulacro_id=simulacro_id)
        if fecha_inicio:
            qs = qs.filter(fecha_realizacion__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_realizacion__lte=fecha_fin)

        if not qs.exists():
            messages.warning(request, "No hay resultados para exportar.")
            return redirect('simulacros:resultados_simulacros')

        # Determinar nombre
        grupo_obj = qs.first().alumno.grupo_actual
        grupo_nombre = grupo_obj.codigo if grupo_obj else "Varios"
        sim_nombre = qs.first().simulacro.nombre
        fecha_pdf = qs.first().fecha_realizacion.strftime("%Y-%m-%d") if qs.first().fecha_realizacion else "N/A"

        filename = f"{grupo_nombre} - {sim_nombre} - {fecha_pdf}.pdf"

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        # ── Documento A4 Landscape ─────────────────────────────────────────
        doc = SimpleDocTemplate(
            response, pagesize=landscape(A4),
            rightMargin=20, leftMargin=20, topMargin=18, bottomMargin=18
        )

        # ── Paleta ────────────────────────────────────────────────────────
        C_AZUL      = colors.HexColor('#1C3A5F')
        C_AZUL2     = colors.HexColor('#2E6DA4')
        C_DORADO    = colors.HexColor('#F5A623')
        C_DORADO_BG = colors.HexColor('#FFF8E1')
        C_VERDE     = colors.HexColor('#27AE60')
        C_VERDE_BG  = colors.HexColor('#D5F5E3')
        C_AMBAR     = colors.HexColor('#F39C12')
        C_NARANJA   = colors.HexColor('#E67E22')
        C_ROJO      = colors.HexColor('#C0392B')
        C_GRIS_CLR  = colors.HexColor('#F4F6F8')
        C_GRIS_MED  = colors.HexColor('#BDC3C7')
        C_GRIS_OSC  = colors.HexColor('#7F8C8D')
        C_BLANCO    = colors.white
        C_NEGRO     = colors.black

        styles = getSampleStyleSheet()

        def ps(name, **kw):
            return ParagraphStyle(name=name, parent=styles['Normal'], **kw)

        sT  = ps('sT',  fontSize=13, fontName='Helvetica-Bold', textColor=C_AZUL,  alignment=1, leading=16)
        sS  = ps('sS',  fontSize=10, fontName='Helvetica-Bold', textColor=C_AZUL,  alignment=1, leading=13)
        sIL = ps('sIL', fontSize=8,  fontName='Helvetica-Bold', textColor=C_AZUL)
        sIV = ps('sIV', fontSize=8,  textColor=C_NEGRO, leading=10)
        sAN = ps('sAN', fontSize=8,  fontName='Helvetica-Bold', textColor=C_AZUL)
        sSC = ps('sSC', fontSize=9,  fontName='Helvetica-Bold', textColor=C_AZUL,  alignment=1)
        sNV = ps('sNV', fontSize=8,  fontName='Helvetica-Bold', alignment=1)
        sSH = ps('sSH', fontSize=8,  fontName='Helvetica-Bold', textColor=C_BLANCO, alignment=1)
        sBd = ps('sBd', fontSize=8,  leading=11)
        sBB = ps('sBB', fontSize=8,  fontName='Helvetica-Bold', leading=11)
        sBu = ps('sBu', fontSize=7.5,leftIndent=6, leading=10)
        sFt = ps('sFt', fontSize=9,  fontName='Helvetica-Bold', textColor=C_AZUL,  alignment=1)
        sND = ps('sND', fontSize=7.5,leading=10, textColor=C_NEGRO)
        sNH = ps('sNH', fontSize=8,  fontName='Helvetica-Bold', textColor=C_AZUL,  leading=11)

        AREA_CFG = [
            ('matematicas',  'puntaje_matematicas', 'MATEMATICAS'),
            ('lectura',      'puntaje_lectura',     'LECTURA CRITICA'),
            ('sociales',     'puntaje_sociales',    'CIENCIAS SOCIALES'),
            ('naturales',    'puntaje_naturales',   'CIENCIAS NATURALES'),
            ('ingles',       'puntaje_ingles',      'INGLES'),
        ]

        def nivel_color(p):
            if p >= 70:   return C_VERDE, 'ALTO'
            elif p >= 55: return C_AMBAR, 'MEDIO'
            else:         return C_NARANJA, 'BAJO'

        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
        elements = []

        for i, res in enumerate(qs):
            nombre = f"{res.alumno.primer_apellido} {res.alumno.segundo_apellido} {res.alumno.nombres}".strip()
            fecha_str = res.fecha_realizacion.strftime('%d de %B de %Y') if res.fecha_realizacion else 'N/A'
            grupo_str = res.alumno.grupo_actual.codigo if res.alumno.grupo_actual else 'N/A'
            pg = int(res.puntaje_global)

            puntajes_res = {
                'matematicas': res.puntaje_matematicas,
                'lectura':     res.puntaje_lectura,
                'sociales':    res.puntaje_sociales,
                'naturales':   res.puntaje_naturales,
                'ingles':      res.puntaje_ingles,
                'global':      res.puntaje_global,
            }
            reporte = generar_reporte_completo(puntajes_res)

            # ── 1. CABECERA ───────────────────────────────────────────────
            if os.path.exists(logo_path):
                logo_cell = RLImage(logo_path, width=52, height=52)
            else:
                logo_cell = Paragraph('', styles['Normal'])

            title_cell = [
                Paragraph('REPORTE POR AREA Y RECOMENDACIONES', sT),
                Paragraph(f'SIMULACRO SABER 11&deg; &ndash; {sim_nombre}', sS),
            ]

            info_data = [
                [Paragraph('<b>Fecha:</b>', sIL),          Paragraph(fecha_str, sIV)],
                [Paragraph('<b>Estudiante:</b>', sIL),     Paragraph(nombre, sIV)],
                [Paragraph('<b>Grupo:</b>', sIL),          Paragraph(grupo_str, sIV)],
                [Paragraph('<b>Puntaje global:</b>', sIL), Paragraph(f'<b>{pg} / 500</b>', sIV)],
            ]
            info_t = Table(info_data, colWidths=[68, 112])
            info_t.setStyle(TableStyle([
                ('FONTSIZE',      (0,0), (-1,-1), 8),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING',    (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 3),
                ('RIGHTPADDING',  (0,0), (-1,-1), 3),
                ('BOX',           (0,0), (-1,-1), 0.6, C_AZUL),
                ('INNERGRID',     (0,0), (-1,-1), 0.3, C_GRIS_MED),
                ('BACKGROUND',    (0,0), (-1,-1), C_GRIS_CLR),
            ]))

            header_t = Table([[logo_cell, title_cell, info_t]], colWidths=[62, 518, 182])
            header_t.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN',         (1,0), (1,0),   'CENTER'),
                ('LEFTPADDING',   (0,0), (-1,-1), 5),
                ('RIGHTPADDING',  (0,0), (-1,-1), 5),
                ('TOPPADDING',    (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 1.2, C_AZUL),
                ('BACKGROUND',    (0,0), (-1,-1), C_GRIS_CLR),
            ]))
            elements.append(header_t)
            elements.append(Spacer(1, 5))

            # ── 2. TABLA DE RESULTADOS + QUE SIGNIFICAN LOS NIVELES ───────
            # Encabezado tabla resultados
            res_header = [
                Paragraph('<b>AREA</b>',              sSH),
                Paragraph('<b>PUNTAJE</b>',           sSH),
                Paragraph('<b>NIVEL DE DESEMPENO</b>',sSH),
                Paragraph('<b>DESEMPENO RELATIVO</b>',sSH),
            ]
            res_rows = [res_header]

            for area_key, attr, label in AREA_CFG:
                p_val = float(getattr(res, attr))
                col_niv, niv_label = nivel_color(p_val)
                hex_niv = col_niv.hexval()
                niv_p = Paragraph(
                    f'<font color="{hex_niv}"><b>&#9679; {niv_label}</b></font>',
                    ps(f'nv_{area_key}', fontSize=8, alignment=1)
                )
                barra = BarraDesempeno(p_val, width=175, height=11)
                res_rows.append([
                    Paragraph(f'<b>{label}</b>', sAN),
                    Paragraph(f'<b>{int(p_val)} / 100</b>', sSC),
                    niv_p,
                    barra,
                ])

            res_t = Table(res_rows, colWidths=[148, 62, 100, 215])
            row_bgs = []
            for r in range(1, len(res_rows)):
                bg = C_GRIS_CLR if r % 2 == 0 else C_BLANCO
                row_bgs.append(('BACKGROUND', (0, r), (-1, r), bg))

            res_t.setStyle(TableStyle([
                ('BACKGROUND',    (0,0),  (-1,0),  C_AZUL),
                ('TEXTCOLOR',     (0,0),  (-1,0),  C_BLANCO),
                ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
                ('FONTSIZE',      (0,0),  (-1,-1), 8),
                ('ALIGN',         (0,0),  (-1,-1), 'CENTER'),
                ('ALIGN',         (0,1),  (0,-1),  'LEFT'),
                ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
                ('TOPPADDING',    (0,0),  (-1,-1), 4),
                ('BOTTOMPADDING', (0,0),  (-1,-1), 4),
                ('LEFTPADDING',   (0,0),  (-1,-1), 5),
                ('RIGHTPADDING',  (0,0),  (-1,-1), 4),
                ('GRID',          (0,0),  (-1,-1), 0.4, C_GRIS_MED),
                ('BOX',           (0,0),  (-1,-1), 0.8, C_AZUL),
            ] + row_bgs))

            # Panel "Que significan los niveles"
            niveles_content = [
                Paragraph('<b>¿QUE SIGNIFICAN LOS NIVELES?</b>',
                          ps('nqt', fontSize=9, fontName='Helvetica-Bold', textColor=C_AZUL, alignment=1)),
                Spacer(1, 6),
                Paragraph('<font color="#27AE60"><b>&#9679; ALTO:</b></font>',    sNH),
                Paragraph('Desempeno superior. Tienes buen dominio de los contenidos evaluados.', sND),
                Spacer(1, 5),
                Paragraph('<font color="#F39C12"><b>&#9679; MEDIO:</b></font>',   sNH),
                Paragraph('Desempeno basico. Tienes conocimientos, pero aun puedes mejorar.', sND),
                Spacer(1, 5),
                Paragraph('<font color="#E67E22"><b>&#9679; BAJO:</b></font>',    sNH),
                Paragraph('Desempeno bajo. Necesitas fortalecer tus conocimientos en esta area.', sND),
            ]
            niveles_t = Table([[niveles_content]], colWidths=[222])
            niveles_t.setStyle(TableStyle([
                ('BOX',           (0,0), (-1,-1), 0.8, C_AZUL2),
                ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#EBF5FB')),
                ('TOPPADDING',    (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 8),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ]))

            mid_t = Table([[res_t, niveles_t]], colWidths=[529, 233])
            mid_t.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('INNERGRID',     (0,0), (-1,-1), 0, C_BLANCO),
                ('ALIGN',         (1,0), (1,0),   'RIGHT'),
            ]))
            elements.append(mid_t)
            elements.append(Spacer(1, 5))

            # ── 3. FORTALEZAS + REC. GENERALES | REC. POR AREA ───────────
            # Fortalezas
            fortalezas_areas = [a for a in reporte['areas'] if a['es_fortaleza']]
            debiles_areas    = [a for a in reporte['areas'] if a['es_critica']]

            fort_items = []
            fort_items.append(Paragraph(
                '<b>FORTALEZAS</b>',
                ps('fh', fontSize=9, fontName='Helvetica-Bold', textColor=C_AZUL, alignment=1)
            ))
            fort_items.append(Spacer(1, 4))
            if fortalezas_areas:
                for fa in fortalezas_areas:
                    fort_items.append(Paragraph(
                        f'<font color="#27AE60"><b>&#10003; {fa["nombre"].upper()}</b></font>', sBB
                    ))
                    if fa['fortalezas']:
                        fort_items.append(Paragraph(fa['fortalezas'][0], sBu))
            else:
                fort_items.append(Paragraph('Sigue practicando para consolidar tus fortalezas.', sBd))

            fort_items.append(Spacer(1, 6))
            fort_items.append(Paragraph(
                '<b>RECOMENDACIONES GENERALES</b>',
                ps('rgh', fontSize=9, fontName='Helvetica-Bold', textColor=C_AZUL, alignment=1)
            ))
            fort_items.append(Spacer(1, 3))
            for rec in reporte['recomendaciones_generales']:
                fort_items.append(Paragraph(f'&#8226; {rec}', sBu))
            if reporte['plan_tiempo']:
                fort_items.append(Spacer(1, 3))
                fort_items.append(Paragraph('<b>Plan de estudio sugerido:</b>', sBB))
                for pt in reporte['plan_tiempo']:
                    fort_items.append(Paragraph(f'  &#8594; {pt}', sBu))

            fort_t = Table([[fort_items]], colWidths=[320])
            fort_t.setStyle(TableStyle([
                ('BOX',           (0,0), (-1,-1), 0.8, C_VERDE),
                ('BACKGROUND',    (0,0), (-1,-1), C_VERDE_BG),
                ('TOPPADDING',    (0,0), (-1,-1), 7),
                ('BOTTOMPADDING', (0,0), (-1,-1), 7),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 8),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ]))

            # Recomendaciones por area
            rec_items = []
            rec_items.append(Paragraph(
                '<b>RECOMENDACIONES POR AREA</b>',
                ps('rah', fontSize=9, fontName='Helvetica-Bold', textColor=C_AZUL, alignment=1)
            ))
            rec_items.append(Spacer(1, 4))
            for area_data in reporte['areas']:
                col_h, _ = nivel_color(area_data['puntaje'])
                hex_h = col_h.hexval()
                rec_items.append(Paragraph(
                    f'<font color="{hex_h}"><b>{area_data["nombre"].upper()}</b></font>', sBB
                ))
                for r in area_data['recomendaciones'][:2]:
                    rec_items.append(Paragraph(f'&#8226; {r}', sBu))

            rec_t = Table([[rec_items]], colWidths=[435])
            rec_t.setStyle(TableStyle([
                ('BOX',           (0,0), (-1,-1), 0.8, C_DORADO),
                ('BACKGROUND',    (0,0), (-1,-1), C_DORADO_BG),
                ('TOPPADDING',    (0,0), (-1,-1), 7),
                ('BOTTOMPADDING', (0,0), (-1,-1), 7),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 8),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ]))

            bot_t = Table([[fort_t, rec_t]], colWidths=[325, 437])
            bot_t.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('ALIGN',         (1,0), (1,0),   'RIGHT'),
            ]))
            elements.append(bot_t)
            elements.append(Spacer(1, 5))

            # ── 4. PIE MOTIVACIONAL ──────────────────────────────────────
            footer_t = Table(
                [[Paragraph('&#9733; &#161;Sigue as&#237;! Con disciplina y constancia alcanzar&#225;s tus metas. &#9733;', sFt)]],
                colWidths=[762]
            )
            footer_t.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), C_DORADO),
                ('TOPPADDING',    (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 0.8, C_AZUL),
            ]))
            elements.append(footer_t)

            if i < len(qs) - 1:
                elements.append(PageBreak())

        doc.build(elements)
        return response


