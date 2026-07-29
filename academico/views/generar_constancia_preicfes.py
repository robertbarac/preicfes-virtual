from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

from academico.models import Clase, Alumno
from usuarios.models import Firma, User

class GenerarConstanciaPreICFESView(UserPassesTestMixin, LoginRequiredMixin, View):
    login_url = '/login/'
    
    def test_func(self):
        # Permitir acceso solo a superusers y miembros del grupo 'SecretariaCartera'
        user = self.request.user
        return user.is_superuser or user.groups.filter(name='SecretariaAcademica').exists()
    def get(self, request, alumno_id):
        alumno = get_object_or_404(Alumno, pk=alumno_id)
        
        # Configurar respuesta PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f"constancia_preicfes_{alumno.primer_apellido}_{alumno.identificacion}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        # Configurar documento
        doc = SimpleDocTemplate(
            response,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
        styles.add(ParagraphStyle(name='SmallCenter', alignment=TA_CENTER, fontSize=8))
        
        # Modificar el estilo Title existente en lugar de crear uno nuevo
        styles['Title'].alignment = TA_CENTER
        styles['Title'].fontSize = 14
        styles['Title'].fontName = 'Helvetica-Bold'
        
        # Contenido
        elements = []
        
        # Logo (escudo)
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img/logo.png')
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=2*inch, height=1*inch))
            elements.append(Spacer(1, 20))
        
        # Fecha actual
        fecha_actual = timezone.localtime(timezone.now()).date()
        
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
        
        # Encabezado
        elements.append(Paragraph('<b>EL PRE ICFES VICTOR VALDEZ</b>', styles['Title']))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph('<b>NIT - 9012725987</b>', styles['Title']))
        elements.append(Spacer(1, 30))
        
        # Cuerpo del certificado
        nombre_completo = f"{alumno.nombres} {alumno.primer_apellido}{' ' + alumno.segundo_apellido if alumno.segundo_apellido else ''}"
        
        # Obtener la fecha de la primera clase del alumno
        primera_clase = None
        try:
            # Intentar obtener la primera clase del grupo actual del alumno
            if alumno.grupo_actual:
                primera_clase = Clase.objects.filter(
                    grupo=alumno.grupo_actual,
                    estado='vista'  # Solo clases que ya se han visto
                ).order_by('fecha').first()
        except Exception as e:
            # Si hay algún error, continuar sin la fecha de la primera clase
            pass
        
        # Usar las fechas de ingreso y culminación del alumno
        dia_inicio = alumno.fecha_ingreso.day
        mes_inicio_en_ingles = alumno.fecha_ingreso.strftime('%B')
        mes_inicio = meses_es.get(mes_inicio_en_ingles, mes_inicio_en_ingles)
        anio_inicio = alumno.fecha_ingreso.year
        
        # Fecha de finalización desde el campo fecha_culminacion
        mes_fin_en_ingles = alumno.fecha_culminacion.strftime('%B')
        mes_fin = meses_es.get(mes_fin_en_ingles, mes_fin_en_ingles)
        anio_fin = alumno.fecha_culminacion.year
        
        # Calcular la duración en meses
        from dateutil.relativedelta import relativedelta
        duracion = relativedelta(alumno.fecha_culminacion, alumno.fecha_ingreso)
        duracion_meses = duracion.months + (duracion.years * 12)
        
        # Obtener las clases del alumno (no simulacros)
        clases_alumno = Clase.objects.filter(
            grupo=alumno.grupo_actual
            # Ya no filtramos por estado para incluir tanto vistas como programadas
        ).exclude(
            horario__in=['08:00-12:00', '08:00-17:00']  # Excluir simulacros
        ).order_by('fecha')
        
        # Determinar los días de la semana en que el alumno tiene clases
        dias_semana = set()
        
        # Verificar si hay clases
        if clases_alumno.exists():
            for clase in clases_alumno:
                dia_semana = clase.fecha.strftime('%A')
                dias_semana.add(dia_semana)
        else:
            # Si no hay clases, usar días predeterminados (lunes a viernes)
            dias_semana = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'}
        
        # Convertir los días de la semana a español
        dias_semana_es = {
            'Monday': 'lunes',
            'Tuesday': 'martes',
            'Wednesday': 'miércoles',
            'Thursday': 'jueves',
            'Friday': 'viernes',
            'Saturday': 'sábado',
            'Sunday': 'domingo'
        }
        
        dias_clases_traducidos = [dias_semana_es.get(dia, dia) for dia in dias_semana]
        
        # Definir el orden correcto de los días de la semana
        orden_dias = {
            'lunes': 0, 'martes': 1, 'miércoles': 2, 'jueves': 3, 
            'viernes': 4, 'sábado': 5, 'domingo': 6
        }
        
        # Ordenar los días de clase según el orden definido
        dias_clases = sorted(dias_clases_traducidos, key=lambda dia: orden_dias.get(dia, 7))
        
        # Formatear los días para el texto
        if len(dias_clases) == 1:
            texto_dias = f"los días {dias_clases[0]}"
        elif len(dias_clases) == 2:
            texto_dias = f"los días {dias_clases[0]} y {dias_clases[1]}"
        else:
            texto_dias = f"los días {', '.join(dias_clases[:-1])} y {dias_clases[-1]}"
        
        # Determinar los horarios de clase
        horas_inicio = set()
        horas_fin = set()
        
        if clases_alumno.exists():
            for clase in clases_alumno:
                hora_inicio = clase.get_hora_inicio()
                hora_fin = clase.get_hora_fin()
                horas_inicio.add(hora_inicio)
                horas_fin.add(hora_fin)
        else:
            # Si no hay clases, usar horarios predeterminados
            from datetime import time
            horas_inicio.add(time(15, 0))  # 3:00 PM
            horas_fin.add(time(17, 0))     # 5:00 PM
        
        # Formatear las horas para el texto
        if horas_inicio and horas_fin:
            hora_inicio_min = min(horas_inicio)
            hora_fin_max = max(horas_fin)
            
            # Formatear en AM/PM
            def formatear_hora(hora):
                hora_12 = hora.strftime('%I:%M')
                # Eliminar cero inicial si existe
                if hora_12.startswith('0'):
                    hora_12 = hora_12[1:]
                ampm = 'am' if hora.hour < 12 else 'pm'
                return f"{hora_12} {ampm}"
            
            texto_horario = f"de {formatear_hora(hora_inicio_min)} hasta las {formatear_hora(hora_fin_max)}"
        else:
            # Si no hay clases, usar un texto genérico
            texto_horario = "en horario regular"
        
        # Añadir cada párrafo por separado
        elements.append(Paragraph("<b>CERTIFICA QUE</b>", styles['Center']))
        elements.append(Spacer(1, 10))
        elements.append(Spacer(1, 20))
        elements.append(Spacer(1, 20))
        elements.append(Spacer(1, 20))
        elements.append(Spacer(1, 20))
        
        
        texto_constancia = f"""Que <b>{nombre_completo}</b>, identificada(o) con {alumno.get_tipo_identificacion_display()} N° <b>{alumno.identificacion}</b>, 
        se encuentra realizando con nosotros el curso de PRE ICFES, al cual ingresó en modalidad presencial {texto_dias} 
        {texto_horario} desde {mes_inicio} del {anio_inicio}. Fecha de finalización del mes de {mes_fin} de {anio_fin}."""
        
        elements.append(Paragraph(texto_constancia, styles['Justify']))
        elements.append(Spacer(1, 20))
        
        # Añadir párrafo de constancia
        texto_para_constancia = f"<para align='justify'>Para mayor constancia, se firma y se sella el presente documento a los {fecha_actual.day} días del mes de {mes_actual_es} de {fecha_actual.year}.</para>"
        elements.append(Paragraph(texto_para_constancia, styles['Justify']))
        
        elements.append(Spacer(1, 40))
        
        elements.append(Spacer(1, 30))
        elements.append(Spacer(1, 30))
        elements.append(Spacer(1, 30))

        try:
            # Usar la firma del usuario actual que está generando el certificado
            coordinador = request.user
                
            firma = Firma.objects.get(usuario=coordinador)
            # Si tiene firma digital, agregarla al documento
            if firma.imagen and os.path.exists(firma.imagen.path):
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
        except (Firma.DoesNotExist, User.DoesNotExist):
            # Si no tiene firma registrada, mostrar la línea
            elements.append(Paragraph("___________________________________________", styles['Center']))
        
        # Datos del usuario que genera el documento
        nombre_completo = f"{coordinador.first_name} {coordinador.last_name}"
        if not nombre_completo.strip():
            nombre_completo = coordinador.username
            
        elements.append(Paragraph(f"<b>{nombre_completo}</b>", styles['Center']))
        
        elements.append(Spacer(1, 40))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>COORDINADOR(A) ACADÉMICO(A) PRE ICFES VICTOR VALDEZ</b>", styles['Center']))
        
        # Agregar teléfono si está disponible
        telefono = coordinador.telefono if hasattr(coordinador, 'telefono') and coordinador.telefono else ""
        if telefono:
            elements.append(Paragraph(f"Cel: {telefono}", styles['Center']))
        
        
        # Pie de página en letras pequeñas
        elements.append(Paragraph("<b>VALDEZ Y ANDRADE SOLUCIONES S.A.S</b>", styles['SmallCenter']))
        elements.append(Paragraph("<b>NIT 901.272.598 - 7</b>", styles['SmallCenter']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("CRA. 60A # 29 - 47 BARRIO LOS ANGELES", styles['SmallCenter']))
        
        # Generar PDF
        doc.build(elements)
        return response