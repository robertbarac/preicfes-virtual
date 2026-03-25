from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Avg, F
from ..models.talleres import IntentoTaller
from ..models.simulacros import IntentoSimulacro

class MisCalificacionesView(LoginRequiredMixin, TemplateView):
    template_name = 'evaluaciones/mis_calificaciones.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Obtener los intentos de talleres del usuario
        context['intentos_talleres'] = IntentoTaller.objects.filter(
            usuario=user,
            fecha_fin__isnull=False # Solo los completados
        ).select_related('taller', 'taller__modulo').order_by('-fecha_inicio')
        
        # Obtener los intentos de simulacros del usuario
        context['intentos_simulacros'] = IntentoSimulacro.objects.filter(
            usuario=user,
            fecha_fin__isnull=False # Solo completados
        ).select_related('simulacro', 'simulacro__modulo').order_by('-fecha_inicio')
        
        # Calcular promedio por materia (Solo el mejor intento de cada taller cuenta)
        # 1. Agrupar por taller y obtener el maximo puntaje
        mejores_intentos = IntentoTaller.objects.filter(
            usuario=user,
            fecha_fin__isnull=False
        ).values(
            'taller_id',
            'taller__tema__materia__nombre'
        ).annotate(
            mejor_puntaje=Max('puntaje_porcentaje')
        )
        
        # 2. Agrupar manualmente por materia para sacar el promedio
        promedios_materia = {}
        for item in mejores_intentos:
            materia = item['taller__tema__materia__nombre']
            if not materia:
                materia = "Sin Materia Asignada"
                
            if materia not in promedios_materia:
                promedios_materia[materia] = {'suma': 0, 'conteo': 0}
            
            promedios_materia[materia]['suma'] += item['mejor_puntaje']
            promedios_materia[materia]['conteo'] += 1
            
        # 3. Formatear para la plantilla
        promedios_finales = []
        for materia, datos in promedios_materia.items():
            promedio = datos['suma'] / datos['conteo']
            promedios_finales.append({
                'materia': materia,
                'promedio': round(promedio, 1),
                'talleres_completados': datos['conteo']
            })
            
        # Ordenar alfabéticamente
        promedios_finales.sort(key=lambda x: x['materia'])
        context['promedios_materia'] = promedios_finales
        
        return context

import io
from django.http import FileResponse
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

User = get_user_model()

@method_decorator(staff_member_required, name='dispatch')
class ReporteEstudiantePDFView(View):
    def get(self, request, *args, **kwargs):
        estudiante_id = self.kwargs.get('pk')
        estudiante = get_object_or_404(User, pk=estudiante_id)
        
        # Recolectar datos
        intentos_simulacros = IntentoSimulacro.objects.filter(
            usuario=estudiante, fecha_fin__isnull=False
        ).select_related('simulacro').order_by('-fecha_inicio')
        
        from django.db.models import Max
        mejores_intentos = IntentoTaller.objects.filter(
            usuario=estudiante, fecha_fin__isnull=False
        ).values('taller_id', 'taller__tema__materia__nombre').annotate(
            mejor_puntaje=Max('puntaje_porcentaje')
        )
        
        promedios_materia = {}
        for item in mejores_intentos:
            materia = item['taller__tema__materia__nombre'] or "Sin Materia Asignada"
            if materia not in promedios_materia:
                promedios_materia[materia] = {'suma': 0, 'conteo': 0}
            promedios_materia[materia]['suma'] += item['mejor_puntaje']
            promedios_materia[materia]['conteo'] += 1
            
        promedios_finales = [
            {'materia': k, 'promedio': v['suma'] / v['conteo'], 'talleres': v['conteo']}
            for k, v in promedios_materia.items()
        ]
        promedios_finales.sort(key=lambda x: x['materia'])

        # Crear PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Reporte de Rendimiento - PreICFES Virtual V.V.")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Estudiante: {estudiante.get_full_name() or estudiante.username}")
        if estudiante.numero_documento:
            p.drawString(50, height - 85, f"Documento: {estudiante.numero_documento}")
            
        y = height - 120
        
        # Sección Simulacros
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Historial de Simulacros")
        y -= 20
        
        p.setFont("Helvetica", 10)
        if intentos_simulacros.exists():
            for intento in intentos_simulacros:
                texto = f"- {intento.simulacro.titulo}: {intento.puntaje_global or 0} / 500 Puntos"
                p.drawString(60, y, texto)
                y -= 15
        else:
            p.drawString(60, y, "No hay simulacros completados.")
            y -= 15
            
        y -= 20
        
        # Sección Talleres (Promedios)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Promedio de Talleres por Materia")
        y -= 20
        
        p.setFont("Helvetica", 10)
        if promedios_finales:
            for item in promedios_finales:
                texto = f"- {item['materia']}: {item['promedio']:.1f}% ({item['talleres']} talleres realizados)"
                p.drawString(60, y, texto)
                y -= 15
        else:
            p.drawString(60, y, "No hay talleres completados.")
            y -= 15
            
        # Generar firma al pie
        p.setFont("Helvetica-Oblique", 9)
        p.drawString(50, 50, "Documento generado automáticamente por el sistema PreICFES Virtual.")
        
        p.showPage()
        p.save()
        buffer.seek(0)
        
        from django.utils import timezone
        ahora_str = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        nombre_base = f"{estudiante.first_name} {estudiante.last_name}".strip().replace(" ", "_")
        if not nombre_base:
            nombre_base = estudiante.username
            
        filename = f"reporte_de_notas_{nombre_base}_{ahora_str}.pdf"
        return FileResponse(buffer, as_attachment=False, filename=filename)


# ─── Reporte de Rendimiento (Staff) ──────────────────────────────────────────
import json
from collections import defaultdict
from django.db.models import Avg, Count, Sum, Max as DjMax
from django.db.models import IntegerField
from django.db.models.functions import Cast

@method_decorator(staff_member_required, name='dispatch')
class ReporteRendimientoView(TemplateView):
    template_name = 'evaluaciones/reporte_rendimiento.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Extraer el filtro de materia desde el GET
        filtro_materia_id = self.request.GET.get('materia')
        try:
            filtro_materia_id = int(filtro_materia_id) if filtro_materia_id else None
        except (ValueError, TypeError):
            filtro_materia_id = None

        # ── 1. Promedio por taller (gráfica) ──────────────────────────────────
        # Filtramos talleres que SI tengan materia asociada, y por filtro si existe.
        talleres_qs = IntentoTaller.objects.filter(
            fecha_fin__isnull=False, 
            puntaje_porcentaje__isnull=False,
            taller__tema__materia__isnull=False
        )
        if filtro_materia_id:
            talleres_qs = talleres_qs.filter(taller__tema__materia_id=filtro_materia_id)

        promedios_por_taller = (
            talleres_qs
            .values('taller__titulo', 'taller__modulo__nombre')
            .annotate(promedio=Avg('puntaje_porcentaje'), total=Count('id'))
            .order_by('taller__modulo__nombre', 'taller__titulo')
        )
        chart_labels = [r['taller__titulo'] for r in promedios_por_taller]
        chart_values = [round(r['promedio'], 1) for r in promedios_por_taller]
        chart_counts = [r['total'] for r in promedios_por_taller]
        context['chart_data'] = json.dumps({
            'labels': chart_labels,
            'values': chart_values,
            'counts': chart_counts,
        })

        # ── 2. Tabla: promedio por estudiante y materia ───────────────────────
        from curriculo.models.core import Materia
        materias = list(Materia.objects.order_by('nombre'))
        estudiantes = list(
            User.objects.filter(is_staff=False, is_active=True)
            .order_by('last_name', 'first_name')
        )

        mejores = (
            IntentoTaller.objects
            .filter(fecha_fin__isnull=False, puntaje_porcentaje__isnull=False)
            .values('usuario_id', 'taller_id', 'taller__tema__materia_id',
                    'taller__tema__materia__nombre')
            .annotate(mejor=DjMax('puntaje_porcentaje'))
        )

        datos = defaultdict(lambda: defaultdict(list))
        for m in mejores:
            if m['taller__tema__materia_id']:
                datos[m['usuario_id']][m['taller__tema__materia_id']].append(m['mejor'])

        tabla = []
        for est in estudiantes:
            filas_materia = []
            for mat in materias:
                if filtro_materia_id and mat.id != filtro_materia_id:
                    continue
                puntajes = datos[est.id].get(mat.id, [])
                if puntajes:
                    filas_materia.append({
                        'materia': mat.nombre,
                        'promedio': round(sum(puntajes) / len(puntajes), 1),
                        'talleres': len(puntajes),
                    })
            if filas_materia:
                tabla.append({
                    'estudiante': est.get_full_name() or est.username,
                    'filas': filas_materia,
                })

        context['tabla'] = tabla
        context['materias'] = materias
        context['filtro_materia_id'] = filtro_materia_id

        # ── 3. Top/Bottom 3 ejes temáticos ────────────────────────────────────
        from ..models.talleres import RespuestaTaller

        respuestas_qs = RespuestaTaller.objects.filter(pregunta__tema__isnull=False)
        if filtro_materia_id:
            respuestas_qs = respuestas_qs.filter(pregunta__tema__materia_id=filtro_materia_id)

        aciertos_por_tema = (
            respuestas_qs
            .values('pregunta__tema__nombre', 'pregunta__tema__materia__nombre')
            .annotate(total=Count('id'), correctas=Sum(Cast('es_correcta', output_field=IntegerField())))
            .filter(total__gte=5)
        )

        temas_lista = []
        for t in aciertos_por_tema:
            pct = round((t['correctas'] / t['total']) * 100, 1) if t['total'] else 0
            temas_lista.append({
                'tema': t['pregunta__tema__nombre'],
                'materia': t['pregunta__tema__materia__nombre'] or '—',
                'porcentaje': pct,
                'total': t['total'],
            })

        temas_lista.sort(key=lambda x: x['porcentaje'], reverse=True)
        context['top_temas'] = temas_lista[:3]
        context['bottom_temas'] = list(reversed(temas_lista[-3:])) if len(temas_lista) >= 3 else temas_lista

        return context



