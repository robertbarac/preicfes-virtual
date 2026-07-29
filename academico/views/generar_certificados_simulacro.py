from django.views import View
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.conf import settings
from django.utils import timezone
import os
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

from academico.models import Clase, Alumno
from usuarios.models import Firma, User

class GenerarCertificadosSimulacroView(View):
    def get(self, request, clase_id):
        try:
            clase = get_object_or_404(Clase, pk=clase_id)
            alumnos = Alumno.objects.filter(grupo_actual=clase.grupo)
            
            if not alumnos.exists():
                raise Http404("No hay alumnos en este grupo")
            
            response = HttpResponse(content_type='application/pdf')
            filename = f"certificados_simulacro_{clase.fecha.strftime('%Y%m%d')}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=40,
                leftMargin=40,
                topMargin=40,
                bottomMargin=40
            )
            
            # Obtener estilos y modificar en lugar de redefinir
            styles = getSampleStyleSheet()
            
            # Modificar el estilo 'Title' existente en lugar de crear uno nuevo
            styles['Title'].alignment = TA_CENTER
            styles['Title'].fontSize = 14
            styles['Title'].fontName = 'Helvetica-Bold'
            
            # Crear estilos personalizados si no existen
            if 'Center' not in styles:
                styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
            if 'Justify' not in styles:
                styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
            
            # Estilo para el pie de página (letras pequeñas)
            styles.add(ParagraphStyle(name='SmallCenter', alignment=TA_CENTER, fontSize=8))
            
            # Fecha actual
            fecha_actual = timezone.now().date()
            
            # Diccionario para convertir nombres de meses en inglés a español
            meses_es = {
                'January': 'enero',
                'February': 'febrero',
                'March': 'marzo',
                'April': 'abril',
                'May': 'mayo',
                'June': 'junio',
                'July': 'julio',
                'August': 'agosto',
                'September': 'septiembre',
                'October': 'octubre',
                'November': 'noviembre',
                'December': 'diciembre'
            }
            
            # Obtener el mes actual en español
            mes_actual_es = meses_es.get(fecha_actual.strftime('%B'), fecha_actual.strftime('%B'))
            
            # Obtener el mes de la clase en español
            mes_clase_es = meses_es.get(clase.fecha.strftime('%B'), clase.fecha.strftime('%B'))
            
            elements = []
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'img/logo.png')

            try:
                # Buscar la firma del usuario actual
                coordinador = request.user
                firma = Firma.objects.get(usuario=coordinador)
            except (Firma.DoesNotExist, User.DoesNotExist):
                firma = None
            
            for alumno in alumnos:
                if os.path.exists(logo_path):
                    elements.append(Image(logo_path, width=2*inch, height=1*inch))
                    elements.append(Spacer(1, 20))
                
                # Encabezado
                elements.append(Paragraph('<b>EL PRE ICFES VICTOR VALDEZ</b>', styles['Title']))
                elements.append(Spacer(1, 10))
                elements.append(Paragraph('<b>NIT - 9012725987</b>', styles['Title']))
                elements.append(Spacer(1, 20))
                elements.append(Paragraph('<b>HACE CONSTAR QUE</b>', styles['Center']))
                elements.append(Spacer(1, 20))
                elements.append(Spacer(1, 20))
                elements.append(Spacer(1, 20))
                elements.append(Spacer(1, 20))
                
                # Cuerpo del certificado
                nombre_completo = f"{alumno.nombres} {alumno.primer_apellido}{' ' + alumno.segundo_apellido if alumno.segundo_apellido else ''}"
                
                texto_certificado = f"""
                <para align=justify>
                <b>{nombre_completo}</b>, identificado(a) con {alumno.get_tipo_identificacion_display()}, N° <b>{alumno.identificacion}</b>, 
                se encuentra realizando el curso de PRE ICFES en nuestra Institución, el día {clase.fecha.day} de {mes_clase_es} del presente año. 
                Estará realizando un simulacro de jornada completa en los horarios de 8:00 AM a 12:00 PM y de 1:00 PM a 5:00 PM
                </para>
                """
                
                elements.append(Paragraph(texto_certificado, styles['Justify']))
                elements.append(Spacer(1, 40))
                
                
                # Texto de constancia
                elements.append(Paragraph(
                    f"<para align='justify'>Para mayor constancia se firma y se sella a los ({fecha_actual.day}) días del mes de {mes_actual_es} de {fecha_actual.year}.</para>",
                    styles['Justify']
                ))
                elements.append(Spacer(1, 50))
                elements.append(Spacer(1, 40))
                elements.append(Spacer(1, 40))
                
                # Firma
                if firma and firma.imagen and os.path.exists(firma.imagen.path):
                    # Agregar la imagen de la firma
                    firma_img = Image(firma.imagen.path)
                    # Ajustar el tamaño de la imagen para que se vea bien en el PDF
                    firma_img.drawHeight = 0.5*inch
                    firma_img.drawWidth = 2*inch
                    elements.append(firma_img)
                    elements.append(Spacer(1, 5))
                else:
                    # Si no tiene imagen de firma, mostrar la línea
                    elements.append(Paragraph("___________________________________________", styles['Center']))
                
                # Datos del usuario que genera el documento
                nombre_completo_usuario = f"{request.user.first_name} {request.user.last_name}"
                if not nombre_completo_usuario.strip():
                    nombre_completo_usuario = request.user.username
                    
                elements.append(Paragraph(f"<b>{nombre_completo_usuario}</b>", styles['Center']))
                elements.append(Paragraph("<b>COORDINADOR(A) ACADÉMICO(A) PRE ICFES VICTOR VALDEZ</b>", styles['Center']))
                
                # Agregar teléfono si está disponible
                telefono = request.user.telefono if hasattr(request.user, 'telefono') and request.user.telefono else ""
                if telefono:
                    elements.append(Paragraph(f"Cel: {telefono}", styles['Center']))
                elements.append(Spacer(1, 30))
                
                # Pie de página en letras pequeñas
                elements.append(Paragraph("<b>VALDEZ Y ANDRADE SOLUCIONES S.A.S</b>", styles['SmallCenter']))
                elements.append(Paragraph("<b>NIT 901.272.598 - 7</b>", styles['SmallCenter']))
                elements.append(Spacer(1, 10))
                elements.append(Paragraph("CRA. 60A # 29 - 47 BARRIO LOS ANGELES", styles['SmallCenter']))
                
                if alumno != alumnos.last():
                    elements.append(PageBreak())
            
            doc.build(elements)
            response.write(buffer.getvalue())
            buffer.close()
            return response
            
        except Exception as e:
            raise Http404(f"Error al generar certificados: {str(e)}")