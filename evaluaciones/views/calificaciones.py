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
        
        filename = f"reporte_{estudiante.username}.pdf"
        return FileResponse(buffer, as_attachment=False, filename=filename)

import io
from django.http import FileResponse
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch

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
        p.drawString(50, 50, "Documento generado automáticamente por sistema PreICFES Virtual.")
        
        p.showPage()
        p.save()
        buffer.seek(0)
        
        filename = f"reporte_{estudiante.username}.pdf"
        return FileResponse(buffer, as_attachment=False, filename=filename)
