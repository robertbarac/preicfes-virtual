import os
from io import BytesIO
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.conf import settings
from django.utils import timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from cartera.models import Cuota
from academico.models import Alumno
from usuarios.models import Firma

class ReciboPDFView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('cartera.change_cuota')

    def handle_no_permission(self):
        return HttpResponseForbidden("No tienes permisos para acceder a esta página.")

    def get(self, request, pk):
        cuota = get_object_or_404(Cuota, pk=pk)
        
        # Crear el PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="recibo_{cuota.id}.pdf"'
        
        # Configurar el documento con márgenes más pequeños
        doc = SimpleDocTemplate(
            response,
            pagesize=letter,
            rightMargin=0.5*cm,
            leftMargin=0.5*cm,
            topMargin=0.5*cm,
            bottomMargin=0.5*cm
        )
        
        # Estilos personalizados para un formato más compacto
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Center', 
            alignment=TA_CENTER,
            fontSize=10,
            leading=12
        ))
        styles.add(ParagraphStyle(
            name='Small', 
            alignment=TA_LEFT,
            fontSize=8,
            leading=10
        ))
        styles.add(ParagraphStyle(
            name='SmallCenter', 
            alignment=TA_CENTER,
            fontSize=8,
            leading=10
        ))
        
        # Contenido
        elements = []
        
        # Función para generar un recibo individual
        def add_recibo(elements, copia_text):
            # Logo y encabezado
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'img/logo.png')
            if os.path.exists(logo_path):
                elements.append(Image(logo_path, width=1.5*inch, height=0.75*inch))
            
            # Títulos
            elements.append(Paragraph('<b>PRE-ICFES VICTOR VALDEZ</b>', styles['Center']))
            elements.append(Paragraph('<b>NIT - 9012725987</b>', styles['SmallCenter']))
            elements.append(Paragraph(f'<b>RECIBO DE PAGO - {copia_text}</b>', styles['Center']))
            elements.append(Spacer(1, 0.2*cm))
            
            # Datos del recibo
            data = [
                ['Nombres:', f'{cuota.deuda.alumno.nombres}'],
                ['Apellidos:', f'{cuota.deuda.alumno.primer_apellido} {cuota.deuda.alumno.segundo_apellido or ""}'],
                ['ID:', f'{dict(Alumno.TIPO_IDENTIFICACION)[cuota.deuda.alumno.tipo_identificacion]}: {cuota.deuda.alumno.identificacion}'],
                ['Tipo programa:', f'{cuota.deuda.alumno.tipo_programa}'],
                ['Fecha Venc.:', f'{cuota.fecha_vencimiento.strftime("%d/%m/%Y")}'],
                ['Fecha Pago:', f'{cuota.fecha_pago.strftime("%d/%m/%Y") if cuota.fecha_pago else "No pagada"}'],
                ['Monto Abonado:', f'${cuota.monto_abonado:.1f}'],
                ['Método de Pago:', f'{cuota.metodo_pago}'],
                ['Saldo Pendiente:', f'${cuota.deuda.saldo_pendiente:.1f}'],
                ['Valor Total:', f'${cuota.deuda.valor_total:.1f}']
            ]
            
            # Tabla de datos con formato más compacto
            table = Table(data, colWidths=[1.5*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('FONT', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 8),  # Tamaño de letra más pequeño
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),  # Líneas más delgadas
                ('BOTTOMPADDING', (0,0), (-1,-1), 1),  # Menos espacio
                ('TOPPADDING', (0,0), (-1,-1), 1)  # Menos espacio
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.3*cm))
            
            # Firma del usuario que genera el recibo
            try:
                # Intentar obtener la imagen de la firma del usuario
                firma = Firma.objects.get(usuario=request.user)
                if firma.imagen and os.path.exists(firma.imagen.path):
                    elements.append(Image(firma.imagen.path, width=2*inch, height=0.5*inch))
                else:
                    # Si no hay imagen o no existe en el sistema de archivos, mostrar línea
                    elements.append(Paragraph('__________________________', styles['SmallCenter']))
            except Firma.DoesNotExist:
                # Si el usuario no tiene firma, mostrar línea
                elements.append(Paragraph('__________________________', styles['SmallCenter']))
            
            # Nombre del usuario
            elements.append(Paragraph(f'Firma: {request.user.get_full_name() or request.user.username}', styles['SmallCenter']))
            elements.append(Spacer(1, 0.2*cm))
            elements.append(Paragraph("<b>Jefe de Cartera del Pre ICFES</b>", styles['SmallCenter']))
            
            # Línea de corte
            elements.append(Paragraph('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -', styles['Small']))
        
        # Añadir primer recibo (copia cliente)
        add_recibo(elements, "COPIA CLIENTE")
        elements.append(Spacer(1, 0.5*cm))
        
        # Añadir segundo recibo (copia negocio)
        add_recibo(elements, "COPIA NEGOCIO")
        
        # Construir el PDF
        doc.build(elements)
        
        return response