# views/pdf.py
# Aquí van DescargarResultadosPDFView y BarraDesempeno

import os

import tempfile
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse

from .resultados import PermisosResultadosMixin

from academico.models import Grupo, Alumno
from ubicaciones.models import Sede
from ..models import Simulacro, ResultadoSimulacro, SimulacroDiagnostico, ResultadoSimulacroDiagnostico
from ..procesar_simulacro import procesar_imagen
from ..calculos import calificar, calcular_puntaje_icfes

# ReportLab imports
from reportlab.lib.pagesizes import A4, landscape, LETTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage, KeepTogether
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from collections import Counter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.units import inch

from ..recomendaciones import generar_reporte_completo
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
            (0,  40, colors.HexColor('#C0392B')),
            (40, 55, colors.HexColor('#E67E22')),
            (55, 70, colors.HexColor('#F1C40F')),
            (70, 100, colors.HexColor('#27AE60')),
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



# ── Función utilitaria: genera los elements de ReportLab para UN resultado ────
def _generar_elements_resultado(res, sim_nombre, use_real_scores=False):
    """
    Genera una lista de Flowables (elements) de ReportLab para un solo
    ResultadoSimulacro. Se usa tanto desde la vista masiva como desde la
    vista individual para respetar el principio DRY.
    """
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

    if use_real_scores:
        AREA_CFG = [
            ('matematicas',  'puntaje_matematicas', 'MATEMATICAS'),
            ('lectura',      'puntaje_lectura',     'LECTURA CRITICA'),
            ('sociales',     'puntaje_sociales',    'CIENCIAS SOCIALES'),
            ('naturales',    'puntaje_naturales',   'CIENCIAS NATURALES'),
            ('ingles',       'puntaje_ingles',      'INGLES'),
        ]
        global_attr = 'puntaje_global'
    else:
        AREA_CFG = [
            ('matematicas',  'puntaje_matematicas_modificado', 'MATEMATICAS'),
            ('lectura',      'puntaje_lectura_modificado',     'LECTURA CRITICA'),
            ('sociales',     'puntaje_sociales_modificado',    'CIENCIAS SOCIALES'),
            ('naturales',    'puntaje_naturales_modificado',   'CIENCIAS NATURALES'),
            ('ingles',       'puntaje_ingles_modificado',      'INGLES'),
        ]
        global_attr = 'puntaje_global_modificado'

    def nivel_color(p):
        if p >= 70:   return C_VERDE, 'ALTO'
        elif p >= 55: return C_AMBAR, 'MEDIO'
        elif p >= 40: return C_NARANJA, 'BÁSICO'
        else:         return C_ROJO, 'BAJO'

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
    elements = []

    nombre = f"{res.alumno.primer_apellido} {res.alumno.segundo_apellido} {res.alumno.nombres}".strip()
    fecha_str = res.fecha_realizacion.strftime('%d de %B de %Y') if res.fecha_realizacion else 'N/A'
    grupo_str = res.alumno.grupo_actual.codigo if res.alumno.grupo_actual else 'N/A'
    pg = int(getattr(res, global_attr))

    puntajes_res = {
        'matematicas': getattr(res, AREA_CFG[0][1]),
        'lectura':     getattr(res, AREA_CFG[1][1]),
        'sociales':    getattr(res, AREA_CFG[2][1]),
        'naturales':   getattr(res, AREA_CFG[3][1]),
        'ingles':      getattr(res, AREA_CFG[4][1]),
        'global':      getattr(res, global_attr),
    }
    reporte = generar_reporte_completo(puntajes_res)

    # ── 1. CABECERA ───────────────────────────────────────────────
    if os.path.exists(logo_path):
        tw = 120
        th = tw * (377.0 / 661.0)
        logo_cell = RLImage(logo_path, width=tw, height=th, kind='proportional')
    else:
        logo_cell = Paragraph('', styles['Normal'])

    title_cell = [
        Paragraph('REPORTE POR AREA Y RECOMENDACIONES', sT),
        Paragraph(f'SIMULACRO SABER 11&deg; &ndash; {sim_nombre}', sS),
    ]

    info_data = [
        [Paragraph('<b>Fecha:</b>', sIL),      Paragraph(fecha_str, sIV)],
        [Paragraph('<b>Estudiante:</b>', sIL), Paragraph(nombre, sIV)],
        [Paragraph('<b>Grupo:</b>', sIL),      Paragraph(grupo_str, sIV)],
    ]
    info_t = Table(info_data, colWidths=[65, 125])
    info_t.setStyle(TableStyle([
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0), (-1,-1), 3),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    score_data = [
        [Paragraph('PUNTAJE GLOBAL', ps('sgl', fontSize=8, fontName='Helvetica-Bold', textColor=C_GRIS_OSC, alignment=1))],
        [Paragraph(f'{pg}', ps('sgv', fontSize=36, fontName='Helvetica-Bold', textColor=C_AZUL, alignment=1, leading=40))],
        [Paragraph('de 500', ps('sgd', fontSize=8, textColor=C_GRIS_OSC, alignment=1))]
    ]
    score_t = Table(score_data, colWidths=[110])
    score_t.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND',    (0,0), (-1,-1), C_BLANCO),
        ('BOX',           (0,0), (-1,-1), 1.5, C_DORADO),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    header_t = Table([[logo_cell, title_cell, info_t, score_t]], colWidths=[120, 320, 190, 132])
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
        Paragraph('Desempeño superior. Tienes buen dominio de los contenidos evaluados.', sND),
        Spacer(1, 4),
        Paragraph('<font color="#F1C40F"><b>&#9679; MEDIO:</b></font>',   sNH),
        Paragraph('Desempeño satisfactorio. Tienes conocimientos, pero aún puedes mejorar.', sND),
        Spacer(1, 4),
        Paragraph('<font color="#E67E22"><b>&#9679; BÁSICO:</b></font>',  sNH),
        Paragraph('Desempeño básico. Debes repasar algunos conceptos fundamentales.', sND),
        Spacer(1, 4),
        Paragraph('<font color="#C0392B"><b>&#9679; BAJO:</b></font>',    sNH),
        Paragraph('Desempeño insuficiente. Necesitas fortalecer tus conocimientos en esta área.', sND),
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

    return elements


class DescargarResultadosPDFView(LoginRequiredMixin, PermisosResultadosMixin, View):
    use_real_scores = False
    
    def get(self, request):
        es_diag = request.GET.get('es_diagnostico') == '1'
        if es_diag:
            qs = ResultadoSimulacroDiagnostico.objects.all().select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('alumno__primer_apellido', 'alumno__segundo_apellido')
        else:
            qs = ResultadoSimulacro.objects.all().select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('alumno__primer_apellido', 'alumno__segundo_apellido')

        sede_id = request.GET.get('sede')
        grupo_id = request.GET.get('grupo')
        simulacro_id = request.GET.get('simulacro')
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')

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

        if not qs.exists():
            messages.warning(request, "No hay resultados para exportar.")
            return redirect('simulacros:resultados_diagnosticos' if es_diag else 'simulacros:resultados_simulacros')

        grupo_obj = qs.first().alumno.grupo_actual
        grupo_nombre = grupo_obj.codigo if grupo_obj else "Varios"
        sim_nombre = qs.first().simulacro.nombre
        fecha_pdf = qs.first().fecha_realizacion.strftime("%Y-%m-%d") if qs.first().fecha_realizacion else "N/A"

        filename = f"{grupo_nombre} - {sim_nombre} - {fecha_pdf}.pdf"

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        doc = SimpleDocTemplate(
            response, pagesize=landscape(LETTER),
            rightMargin=20, leftMargin=20, topMargin=18, bottomMargin=18
        )

        elements = []

        for i, res in enumerate(qs):
            sim_nombre_res = res.simulacro.nombre
            elements.extend(_generar_elements_resultado(res, sim_nombre_res, use_real_scores=self.use_real_scores))
            if i < len(qs) - 1:
                elements.append(PageBreak())

        doc.build(elements)
        return response

class DescargarResultadosRealesPDFView(DescargarResultadosPDFView):
    use_real_scores = True


class DescargarResultadoIndividualPDFView(LoginRequiredMixin, View):
    """Genera el PDF de resultado individual de un ResultadoSimulacro por su PK."""
    
    def get(self, request, resultado_pk):
        res = get_object_or_404(
            ResultadoSimulacro.objects.select_related('alumno', 'simulacro', 'alumno__grupo_actual'),
            pk=resultado_pk
        )
        
        sim_nombre = res.simulacro.nombre
        nombre_alumno = f"{res.alumno.primer_apellido} {res.alumno.segundo_apellido} {res.alumno.nombres}".strip()
        filename = f"Resultado_{nombre_alumno}_{sim_nombre}.pdf"
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        doc = SimpleDocTemplate(
            response, pagesize=landscape(LETTER),
            rightMargin=20, leftMargin=20, topMargin=18, bottomMargin=18
        )
        
        elements = _generar_elements_resultado(res, sim_nombre, use_real_scores=False)
        doc.build(elements)
        return response

class DescargarInformeDirectivoPDFView(LoginRequiredMixin, PermisosResultadosMixin, View):
    def get(self, request):
        es_diag = request.GET.get('es_diagnostico') == '1'
        if es_diag:
            qs = ResultadoSimulacroDiagnostico.objects.all().select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('-puntaje_global_modificado')
        else:
            qs = ResultadoSimulacro.objects.all().select_related('alumno', 'simulacro', 'alumno__grupo_actual').order_by('-puntaje_global_modificado')
        
        sede_id = request.GET.get('sede')
        grupo_id = request.GET.get('grupo')
        simulacro_id = request.GET.get('simulacro')
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')

        if sede_id: qs = qs.filter(alumno__grupo_actual__salon__sede_id=sede_id)
        if grupo_id: qs = qs.filter(alumno__grupo_actual_id=grupo_id)
        if simulacro_id: qs = qs.filter(simulacro_id=simulacro_id)
        if fecha_inicio: qs = qs.filter(fecha_realizacion__gte=fecha_inicio)
        if fecha_fin: qs = qs.filter(fecha_realizacion__lte=fecha_fin)

        if not qs.exists():
            messages.warning(request, "No hay resultados para generar el informe directivo.")
            return redirect('simulacros:resultados_diagnosticos' if es_diag else 'simulacros:resultados_simulacros')

        simulacro = qs.first().simulacro
        total_alumnos = qs.count()

        # Promedios, Min y Max
        puntajes_globales = [r.puntaje_global_modificado for r in qs]
        avg_global = sum(puntajes_globales) / total_alumnos
        max_global = max(puntajes_globales)
        min_global = min(puntajes_globales)
        
        avg_mat = sum(r.puntaje_matematicas_modificado for r in qs) / total_alumnos
        avg_lec = sum(r.puntaje_lectura_modificado for r in qs) / total_alumnos
        avg_soc = sum(r.puntaje_sociales_modificado for r in qs) / total_alumnos
        avg_nat = sum(r.puntaje_naturales_modificado for r in qs) / total_alumnos
        avg_ing = sum(r.puntaje_ingles_modificado for r in qs) / total_alumnos

        # Distribución de Niveles Globales (Pie Chart)
        niveles_global = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}
        for p in puntajes_globales:
            if p >= 350: niveles_global['Alto'] += 1
            elif p >= 250: niveles_global['Medio'] += 1
            elif p >= 150: niveles_global['Básico'] += 1
            else: niveles_global['Bajo'] += 1

        # Distribución por Áreas (Barras Agrupadas)
        niv_mat = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}
        niv_lec = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}
        niv_soc = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}
        niv_nat = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}
        niv_ing = {'Alto': 0, 'Medio': 0, 'Básico': 0, 'Bajo': 0}

        def clasificar_area(p, dict_niv):
            if p >= 70: dict_niv['Alto'] += 1
            elif p >= 55: dict_niv['Medio'] += 1
            elif p >= 40: dict_niv['Básico'] += 1
            else: dict_niv['Bajo'] += 1

        for r in qs:
            clasificar_area(r.puntaje_matematicas_modificado, niv_mat)
            clasificar_area(r.puntaje_lectura_modificado, niv_lec)
            clasificar_area(r.puntaje_sociales_modificado, niv_soc)
            clasificar_area(r.puntaje_naturales_modificado, niv_nat)
            clasificar_area(r.puntaje_ingles_modificado, niv_ing)

        # Análisis de Ítems Críticos
        top_errores = []

        def get_componente_from_item(item_idx, cortes, componentes):
            c_idx = 0
            for c in cortes:
                if item_idx <= c: return componentes[c_idx]
                c_idx += 1
            return componentes[-1] if componentes else "N/A"

        if es_diag:
            errores = Counter()
            sol = getattr(simulacro, 'soluciones', '')
            for r in qs:
                resp = getattr(r, 'respuestas', '')
                if resp and sol:
                    for idx, (ans, s_val) in enumerate(zip(resp, sol)):
                        if ans != s_val:
                            errores[idx + 1] += 1
            
            p_corte = getattr(simulacro, 'puntos_corte', [])
            cortes = p_corte if isinstance(p_corte, list) else (p_corte.get('cortes', []) if isinstance(p_corte, dict) else [])
            comp = simulacro.get_componentes() if hasattr(simulacro, 'get_componentes') else []
            
            for item, count in errores.most_common(50):
                pct = (count / total_alumnos) * 100
                c_nombre = get_componente_from_item(item, cortes, comp).upper()
                top_errores.append(['SD', item, c_nombre, pct, count])
            top_errores.sort(key=lambda x: x[3], reverse=True)
            top_errores = top_errores[:50]
        else:
            errores_s1 = Counter()
            errores_s2 = Counter()
            sol_s1 = getattr(simulacro, 'soluciones_s1', '')
            sol_s2 = getattr(simulacro, 'soluciones_s2', '')
            
            for r in qs:
                resp_s1 = getattr(r, 'respuestas_s1', '')
                resp_s2 = getattr(r, 'respuestas_s2', '')
                if resp_s1 and sol_s1:
                    for idx, (resp, sol) in enumerate(zip(resp_s1, sol_s1)):
                        if resp != sol: errores_s1[idx+1] += 1
                if resp_s2 and sol_s2:
                    for idx, (resp, sol) in enumerate(zip(resp_s2, sol_s2)):
                        if resp != sol: errores_s2[idx+1] += 1

            p_s1 = getattr(simulacro, 'puntos_corte_s1', [])
            p_s2 = getattr(simulacro, 'puntos_corte_s2', [])
            cortes_s1 = p_s1 if isinstance(p_s1, list) else (p_s1.get('cortes', []) if isinstance(p_s1, dict) else [])
            cortes_s2 = p_s2 if isinstance(p_s2, list) else (p_s2.get('cortes', []) if isinstance(p_s2, dict) else [])
            comp_s1 = simulacro.get_componentes_s1() if hasattr(simulacro, 'get_componentes_s1') else []
            comp_s2 = simulacro.get_componentes_s2() if hasattr(simulacro, 'get_componentes_s2') else []

            for item, count in errores_s1.most_common(50):
                pct = (count / total_alumnos) * 100
                comp = get_componente_from_item(item, cortes_s1, comp_s1).upper()
                top_errores.append(['S1', item, comp, pct, count])
                
            for item, count in errores_s2.most_common(50):
                pct = (count / total_alumnos) * 100
                comp = get_componente_from_item(item, cortes_s2, comp_s2).upper()
                top_errores.append(['S2', item, comp, pct, count])
                
            top_errores.sort(key=lambda x: x[3], reverse=True)
            top_errores = top_errores[:50] # Top 50 de ambos cuadernillos combinados

        # Formatear el PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Informe_Directivo_{simulacro.nombre}.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=LETTER, rightMargin=40, leftMargin=40, topMargin=35, bottomMargin=35)
        elements = []
        styles = getSampleStyleSheet()
        
        t_style = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=1, textColor=colors.HexColor('#1C3A5F'), fontSize=16)
        s_style = ParagraphStyle(name='Sub', parent=styles['Normal'], alignment=1, fontSize=11, textColor=colors.HexColor('#7F8C8D'), spaceAfter=20)
        h2 = ParagraphStyle(name='H2', parent=styles['Heading2'], textColor=colors.HexColor('#1C3A5F'), spaceBefore=20, spaceAfter=10)
        p_style = ParagraphStyle(name='p', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#34495E'), spaceAfter=10)
        
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
        if os.path.exists(logo_path):
            elements.append(RLImage(logo_path, width=90, height=90*377/661.0, kind='proportional'))
            
        elements.append(Paragraph('INFORME DIRECTIVO DE RESULTADOS', t_style))
        elements.append(Paragraph(f'Simulacro: {simulacro.nombre} &nbsp;|&nbsp; Estudiantes Evaluados: {total_alumnos}', s_style))
        
        # 1. Resumen Global
        elements.append(Paragraph('1. Desempeño Promedio Grupal', h2))
        elements.append(Paragraph(f"Puntaje Mínimo: <b>{min_global:.0f}</b> &nbsp;|&nbsp; Puntaje Máximo: <b>{max_global:.0f}</b>", p_style))
        t_data = [
            ['GLOBAL', 'Matemáticas', 'Lectura Cr.', 'Sociales', 'Naturales', 'Inglés'],
            [f"{avg_global:.0f}", f"{avg_mat:.0f}", f"{avg_lec:.0f}", f"{avg_soc:.0f}", f"{avg_nat:.0f}", f"{avg_ing:.0f}"]
        ]
        t = Table(t_data, colWidths=[85]*6)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1C3A5F')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F4F6F8')),
            ('FONTSIZE', (0,1), (0,1), 12),
            ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        # Gráfica de Pastel (Distribución Global) y Gráfica de Barras (Promedios)
        d_pie = Drawing(200, 150)
        pie = Pie()
        pie.x = 20
        pie.y = 20
        pie.width = 110
        pie.height = 110
        
        data_pie = [niveles_global['Alto'], niveles_global['Medio'], niveles_global['Básico'], niveles_global['Bajo']]
        labels_pie = []
        for name, val in [('Alto', niveles_global['Alto']), ('Medio', niveles_global['Medio']), ('Básico', niveles_global['Básico']), ('Bajo', niveles_global['Bajo'])]:
            if val > 0:
                pct = (val/total_alumnos)*100
                labels_pie.append(f"{name} ({pct:.0f}%)")
            else:
                labels_pie.append("")
                
        pie.data = [v for v in data_pie if v > 0]
        pie.labels = [l for l in labels_pie if l]
        
        pie_colors = []
        if niveles_global['Alto'] > 0: pie_colors.append(colors.HexColor('#27AE60'))
        if niveles_global['Medio'] > 0: pie_colors.append(colors.HexColor('#F1C40F'))
        if niveles_global['Básico'] > 0: pie_colors.append(colors.HexColor('#E67E22'))
        if niveles_global['Bajo'] > 0: pie_colors.append(colors.HexColor('#C0392B'))
        
        for i, color in enumerate(pie_colors):
            pie.slices[i].fillColor = color
            pie.slices[i].fontName = 'Helvetica-Bold'
            pie.slices[i].fontSize = 8
            
        d_pie.add(pie)

        d_bar = Drawing(300, 150)
        bc = VerticalBarChart()
        bc.x = 30
        bc.y = 30
        bc.height = 100
        bc.width = 240
        bc.data = [[avg_mat, avg_lec, avg_soc, avg_nat, avg_ing]]
        bc.strokeColor = colors.white
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.categoryAxis.labels.boxAnchor = 'ne'
        bc.categoryAxis.labels.dx = 8
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.fontSize = 8
        bc.categoryAxis.categoryNames = ['Mate', 'Lectura', 'Sociales', 'Natu', 'Inglés']
        bc.bars[0].fillColor = colors.HexColor('#2E6DA4')
        
        # Etiquetas arriba de las barras
        bc.barLabelFormat = '%.0f'
        bc.barLabels.nudge = 5
        bc.barLabels.boxAnchor = 's'
        bc.barLabels.fontName = 'Helvetica-Bold'
        bc.barLabels.fontSize = 7
        
        d_bar.add(bc)
        
        graphs_t = Table([[d_pie, d_bar]], colWidths=[200, 315])
        graphs_t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(graphs_t)
        
        # 2. Distribución de Desempeño por Área (Barras Agrupadas)
        elements.append(Paragraph('2. Distribución de Desempeño por Área', h2))
        elements.append(Paragraph('Conteo de estudiantes en niveles Alto (>=70), Medio (>=55), Básico (>=40) y Bajo (<40).', p_style))
        
        d_group = Drawing(500, 160)
        bcg = VerticalBarChart()
        bcg.x = 40
        bcg.y = 20
        bcg.height = 120
        bcg.width = 380
        
        s_alto = [niv_mat['Alto'], niv_lec['Alto'], niv_soc['Alto'], niv_nat['Alto'], niv_ing['Alto']]
        s_medio = [niv_mat['Medio'], niv_lec['Medio'], niv_soc['Medio'], niv_nat['Medio'], niv_ing['Medio']]
        s_basico = [niv_mat['Básico'], niv_lec['Básico'], niv_soc['Básico'], niv_nat['Básico'], niv_ing['Básico']]
        s_bajo = [niv_mat['Bajo'], niv_lec['Bajo'], niv_soc['Bajo'], niv_nat['Bajo'], niv_ing['Bajo']]
        
        bcg.data = [s_alto, s_medio, s_basico, s_bajo]
        bcg.strokeColor = colors.white
        bcg.valueAxis.valueMin = 0
        max_val = max(s_alto + s_medio + s_basico + s_bajo)
        bcg.valueAxis.valueMax = max_val + (5 - max_val % 5) if max_val % 5 != 0 else max_val + 5
        bcg.valueAxis.valueStep = max(1, max_val // 5) if max_val > 0 else 1
        bcg.categoryAxis.labels.boxAnchor = 'n'
        bcg.categoryAxis.labels.dy = -5
        bcg.categoryAxis.labels.fontSize = 9
        bcg.categoryAxis.categoryNames = ['Mate', 'Lectura', 'Sociales', 'Natu', 'Inglés']
        bcg.bars[0].fillColor = colors.HexColor('#27AE60') # Alto
        bcg.bars[1].fillColor = colors.HexColor('#F1C40F') # Medio
        bcg.bars[2].fillColor = colors.HexColor('#E67E22') # Básico
        bcg.bars[3].fillColor = colors.HexColor('#C0392B') # Bajo
        
        # Etiquetas en las barras (oculta el cero si no hay estudiantes en ese nivel)
        bcg.barLabelFormat = lambda x: str(int(x)) if x > 0 else ""
        bcg.barLabels.nudge = 2
        bcg.barLabels.boxAnchor = 's'
        bcg.barLabels.fontName = 'Helvetica'
        bcg.barLabels.fontSize = 6
        
        leg = Legend()
        leg.x = 440
        leg.y = 120
        leg.boxAnchor = 'nw'
        leg.colorNamePairs = [
            (colors.HexColor('#27AE60'), 'Alto'),
            (colors.HexColor('#F1C40F'), 'Medio'),
            (colors.HexColor('#E67E22'), 'Básico'),
            (colors.HexColor('#C0392B'), 'Bajo')
        ]
        leg.fontName = 'Helvetica'
        leg.fontSize = 8
        leg.dxTextSpace = 5
        leg.dy = 5
        leg.dx = 5
        leg.deltay = 12
        leg.strokeColor = colors.black
        leg.strokeWidth = 0.5
        leg.columnMaximum = 4
        d_group.add(bcg)
        d_group.add(leg)
        elements.append(d_group)
        
        elements.append(PageBreak())
        
        # 3. Análisis Crítico
        elements.append(Paragraph('3. Análisis de Ítems Críticos (Top 50 más fallados)', h2))
        err_data = [['#', 'Ses.', 'Preg.', 'Componente Evaluado', 'Alumnos Err.', '% Error']]
        for i, row in enumerate(top_errores, 1):
            err_data.append([str(i), row[0], str(row[1]), row[2], str(row[4]), f"{row[3]:.1f}%"])
            
        if len(err_data) == 1:
            err_data.append(['-', '-', '-', 'No hay errores registrados', '-', '-'])
            
        t_err = Table(err_data, colWidths=[30, 40, 45, 230, 100, 65], repeatRows=1)
        t_err.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#C0392B')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('ALIGN', (3,1), (3,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F4F6F8')]),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_err)
        
        elements.append(PageBreak())
        
        # 4. Escalafón
        elements.append(Paragraph('4. Escalafón de Estudiantes', h2))
        
        top_mat = sorted(list(set(r.puntaje_matematicas_modificado for r in qs)), reverse=True)[:3]
        top_lec = sorted(list(set(r.puntaje_lectura_modificado for r in qs)), reverse=True)[:3]
        top_soc = sorted(list(set(r.puntaje_sociales_modificado for r in qs)), reverse=True)[:3]
        top_nat = sorted(list(set(r.puntaje_naturales_modificado for r in qs)), reverse=True)[:3]
        top_ing = sorted(list(set(r.puntaje_ingles_modificado for r in qs)), reverse=True)[:3]
        top_glb = sorted(list(set(r.puntaje_global_modificado for r in qs)), reverse=True)[:3]
        
        cell_style = ParagraphStyle(name='CellCenter', parent=styles['Normal'], fontSize=8, alignment=1)
        
        def format_score_with_medal(score, top_values):
            score_int = int(score)
            text = f"{score_int}"
            if score in top_values:
                idx = top_values.index(score)
                if idx == 0:
                    text = f'<font color="#F39C12">&#9733;</font> <b>{score_int}</b>' # Oro
                elif idx == 1:
                    text = f'<font color="#7F8C8D">&#9733;</font> <b>{score_int}</b>' # Plata
                elif idx == 2:
                    text = f'<font color="#D35400">&#9733;</font> <b>{score_int}</b>' # Bronce
            return Paragraph(text, cell_style)
        
        esc_data = [['#', 'Estudiante', 'Glob', 'Mate', 'Lect', 'Soci', 'Natu', 'Ingl']]
        for rank, r in enumerate(qs, 1):
            nombre = f"{r.alumno.primer_apellido} {r.alumno.segundo_apellido} {r.alumno.nombres}"
            
            # Truncar nombre si es muy largo
            if len(nombre) > 35:
                nombre = nombre[:32] + "..."
                
            esc_data.append([
                str(rank), 
                Paragraph(nombre, ParagraphStyle(name='CellLeft', parent=styles['Normal'], fontSize=8)), 
                format_score_with_medal(r.puntaje_global_modificado, top_glb),
                format_score_with_medal(r.puntaje_matematicas_modificado, top_mat),
                format_score_with_medal(r.puntaje_lectura_modificado, top_lec),
                format_score_with_medal(r.puntaje_sociales_modificado, top_soc),
                format_score_with_medal(r.puntaje_naturales_modificado, top_nat),
                format_score_with_medal(r.puntaje_ingles_modificado, top_ing),
            ])
            
        t_esc = Table(esc_data, colWidths=[25, 215, 40, 39, 39, 39, 39, 39], repeatRows=1)
        t_esc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1C3A5F')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (2,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F4F6F8')]),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t_esc)
        
        doc.build(elements)
        return response
