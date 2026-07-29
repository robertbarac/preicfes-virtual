import os
from io import BytesIO
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

from academico.models import Alumno
from cartera.models import Deuda
from usuarios.models import Firma


class PazSalvoPDFView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        # Usar un permiso específico en lugar de un nombre de grupo hardcodeado
        return self.request.user.is_superuser or self.request.user.has_perm('cartera.add_paz_y_salvo')

    def handle_no_permission(self):
        return HttpResponseForbidden("No tienes permisos para acceder a esta página.")

    def get(self, request, alumno_id):
        alumno = get_object_or_404(Alumno, pk=alumno_id)
        
        try:
            deuda = alumno.deuda  # Accede a la deuda a través del related_name
            if not (deuda.estado == 'pagada' and deuda.saldo_pendiente == 0):
                return HttpResponseForbidden("El alumno no está a paz y salvo")
                
        except Deuda.DoesNotExist:
            return HttpResponseForbidden("El alumno no tiene registros de deuda")

        # Traducción de meses al español
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
        
        # Obtener información adicional para el certificado
        # Usar fecha_ingreso y fecha_culminacion del alumno
        horario_clase = "8:00 a.m. a 11:00 a.m."  # Horario por defecto
        dias_semana = []
        
        # Buscar clases del alumno a través de su grupo actual
        if alumno.grupo_actual:
            # Filtrar clases excluyendo las de materia 'Simulacro'
            clases = alumno.grupo_actual.clases.all().select_related('materia').order_by('fecha')
            clases_regulares = clases.exclude(materia__nombre__icontains='Simulacro').filter(estado='vista')
            
            if clases_regulares.exists():
                # Determinar los días de la semana en que asiste
                dias_semana = set()
                for clase in clases_regulares:
                    dia_semana = clase.fecha.strftime('%A')
                    dias_semana.add(dia_semana)
                
                # Traducir días de la semana al español
                traduccion_dias = {
                    'Monday': 'lunes',
                    'Tuesday': 'martes',
                    'Wednesday': 'miércoles',
                    'Thursday': 'jueves',
                    'Friday': 'viernes',
                    'Saturday': 'sábado',
                    'Sunday': 'domingo'
                }
                
                dias_semana = [traduccion_dias.get(dia, dia) for dia in dias_semana]
                
                # Ordenar los días de la semana en orden cronológico
                orden_dias = {'lunes': 1, 'martes': 2, 'miércoles': 3, 'jueves': 4, 'viernes': 5, 'sábado': 6, 'domingo': 7}
                dias_semana.sort(key=lambda x: orden_dias.get(x, 8))
                
                # Determinar los horarios de clase
                horas_inicio = set()
                horas_fin = set()
                
                for clase in clases_regulares:
                    hora_inicio = clase.get_hora_inicio()
                    hora_fin = clase.get_hora_fin()
                    horas_inicio.add(hora_inicio)
                    horas_fin.add(hora_fin)
                
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
                    
                    horario_clase = f"{formatear_hora(hora_inicio_min)} a {formatear_hora(hora_fin_max)}"
        
        # Calcular duración del curso en meses usando fecha_ingreso y fecha_culminacion
        from dateutil.relativedelta import relativedelta
        duracion = relativedelta(alumno.fecha_culminacion, alumno.fecha_ingreso)
        duracion_meses = duracion.months + (duracion.years * 12)
        if duracion_meses == 0:
            duracion_meses = 1  # Mínimo 1 mes
        
        # Diccionario para convertir números a texto en español
        numeros_texto = {
            1: 'uno',
            2: 'dos',
            3: 'tres',
            4: 'cuatro',
            5: 'cinco',
            6: 'seis',
            7: 'siete',
            8: 'ocho',
            9: 'nueve',
            10: 'diez',
            11: 'once',
            12: 'doce'
        }
        
        # Obtener el texto del número de meses
        duracion_meses_texto = numeros_texto.get(duracion_meses, str(duracion_meses))
        
        # Configurar documento
        response = HttpResponse(content_type='application/pdf')
        filename = f"paz_salvo_{alumno.primer_apellido}_{alumno.identificacion}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
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
        styles.add(ParagraphStyle(name='Justify', alignment=4))
        styles.add(ParagraphStyle(name='Center', alignment=1))
        
        # Contenido
        elements = []
        
        # Logo (opcional)
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img/logo.png')
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=2*inch, height=1*inch))
            elements.append(Spacer(1, 20))
        
        # Encabezado
        elements.append(Paragraph('<b>EL PRE ICFES VICTOR VALDEZ</b>', styles['Center']))
        elements.append(Paragraph('<b>NIT: 901.272.598-7</b>', styles['Center']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph('<b>' + '_'*50 + '</b>', styles['Center']))
        elements.append(Paragraph('<b>HACE CONSTAR</b>', styles['Center']))
        elements.append(Paragraph('<b>' + '_'*50 + '</b>', styles['Center']))
        elements.append(Spacer(1, 20))
        
        # Fecha actual formateada
        fecha_actual = timezone.now().date()
        mes_actual_en_ingles = fecha_actual.strftime("%B")
        mes_actual_es = meses_es.get(mes_actual_en_ingles, mes_actual_en_ingles)
        fecha_str = f"{fecha_actual.day} de {mes_actual_es} de {fecha_actual.year}"
        
        # Texto para los días de la semana
        texto_dias = "los días establecidos en el horario"
        if len(dias_semana) > 0:
            # Verificar si asiste de lunes a viernes
            dias_laborables = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
            if all(dia in dias_semana for dia in dias_laborables) and len(dias_semana) == 5:
                texto_dias = "de lunes a viernes"
            # Verificar si asiste de lunes a sábado
            elif all(dia in dias_semana for dia in dias_laborables + ['sábado']) and len(dias_semana) == 6:
                texto_dias = "de lunes a sábado"
            # Caso especial para sábado
            elif len(dias_semana) == 1 and 'sábado' in dias_semana:
                texto_dias = "los días sábados"
            # Caso especial para domingo
            elif len(dias_semana) == 1 and 'domingo' in dias_semana:
                texto_dias = "los días domingos"
            # Caso para días consecutivos (ej: lunes a miércoles)
            elif len(dias_semana) >= 2:
                # Verificar si los días son consecutivos
                indices = [orden_dias[dia] for dia in dias_semana]
                indices.sort()
                if indices == list(range(min(indices), max(indices) + 1)) and max(indices) - min(indices) + 1 == len(indices):
                    texto_dias = f"de {dias_semana[0]} a {dias_semana[-1]}"
                else:
                    texto_dias = f"los días {', '.join(dias_semana)}"
        
        
        # Mes y año de finalización desde fecha_culminacion
        mes_en_ingles = alumno.fecha_culminacion.strftime("%B")
        mes_finalizacion = meses_es.get(mes_en_ingles, mes_en_ingles)
        anio_finalizacion = alumno.fecha_culminacion.year
        
        # Fecha de ingreso desde fecha_ingreso
        dia = alumno.fecha_ingreso.day
        mes_en_ingles = alumno.fecha_ingreso.strftime("%B")
        mes = meses_es.get(mes_en_ingles, mes_en_ingles)
        anio = alumno.fecha_ingreso.year
        fecha_ingreso = f"{dia} de {mes} de {anio}"
        
        # Vamos a crear los párrafos por separado para evitar problemas con ReportLab
        # Párrafo 1
        nombre_completo = f"{alumno.nombres} {alumno.primer_apellido}{(' ' + alumno.segundo_apellido) if alumno.segundo_apellido else ''}"
        parrafo1 = Paragraph(
            f"<para align='justify'>Que <b>{nombre_completo}</b>, "
            f"identificado(a) con {alumno.get_tipo_identificacion_display()} <b>{alumno.identificacion}</b>, "
            f"se encuentra realizando el curso de PRE ICFES, al cual ingresó en modalidad presencial desde el día <b>{fecha_ingreso}</b>.</para>", 
            styles['Justify']
        )
        
        # Párrafo 2
        parrafo2 = Paragraph(
            "<para align='justify'>El curso tiene como objetivo preparar académicamente a la estudiante en las diferentes áreas evaluadas "
            "en el examen de Estado Saber 11, reforzando conocimientos, promoviendo estrategias de aprendizaje, y fortaleciendo "
            "habilidades analíticas para garantizar su desempeño óptimo en dicho examen.</para>",
            styles['Justify']
        )
        
        # Párrafo 3
        parrafo3 = Paragraph(
            f"<para align='justify'>La estudiante asiste regularmente {texto_dias} de <b>{horario_clase}</b>, en modalidad presencial. "
            f"El curso tiene una duración total de <b>{duracion_meses_texto} ({duracion_meses})</b> meses, con fecha de finalización "
            f"prevista para el mes de <b>{mes_finalizacion}</b> de <b>{anio_finalizacion}</b>.</para>",
            styles['Justify']
        )
        
        # Párrafo 4
        parrafo4 = Paragraph(
            "<para align='justify'>La estudiante ha cumplido con las obligaciones correspondientes, y se encuentra a paz y salvo en su totalidad de curso, "
            "incluyendo las responsabilidades administrativas y financieras requeridas para su participación en el programa académico.</para>",
            styles['Justify']
        )
        
        # Línea separadora
        linea1 = Paragraph(f"<para align='justify'><b>{'_'*50}</b></para>", styles['Justify'])
        
        # Párrafo 5
        parrafo5 = Paragraph(
            f"<para align='justify'>Para mayor constancia, se firma y se sella el presente documento a los {fecha_actual.day} días "
            f"del mes de {mes_actual_es} de {fecha_actual.year}.</para>",
            styles['Justify']
        )
        
        # Línea separadora final
        linea2 = Paragraph(f"<para align='justify'><b>{'_'*50}</b></para>", styles['Justify'])
        
        # Añadir todos los elementos al documento
        elements.append(parrafo1)
        elements.append(Spacer(1, 10))
        elements.append(parrafo2)
        elements.append(Spacer(1, 10))
        elements.append(parrafo3)
        elements.append(Spacer(1, 10))
        elements.append(parrafo4)
        elements.append(Spacer(1, 15))
        elements.append(linea1)
        elements.append(Spacer(1, 10))
        elements.append(parrafo5)
        elements.append(Spacer(1, 10))
        elements.append(linea2)
        elements.append(Spacer(1, 30))
        
        elements.append(Spacer(1, 30))
        elements.append(Spacer(1, 30))

        # Firma del usuario que genera el documento
        nombre_completo = f"{request.user.first_name} {request.user.last_name}"
        if not nombre_completo.strip():
            nombre_completo = request.user.username
            
        telefono = request.user.telefono if hasattr(request.user, 'telefono') and request.user.telefono else ""
        
        # Buscar si el usuario tiene una firma digital registrada
        try:
            firma = Firma.objects.get(usuario=request.user)
            # Si tiene firma digital, agregarla al documento
            if firma.imagen and os.path.exists(firma.imagen.path):
                print(f"Firma encontrada: {firma.imagen.path}")
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
        except Firma.DoesNotExist:
            # Si no tiene firma registrada, mostrar la línea
            elements.append(Paragraph("___________________________________________", styles['Center']))
        

        # Agregar el nombre y cargo
        elements.append(Paragraph(f"<b>{nombre_completo}</b>", styles['Center']))
        elements.append(Paragraph("<b>Jefe de Cartera del Pre ICFES</b>", styles['Center']))
            
        if telefono:
            elements.append(Paragraph(f"Cel.: {telefono}", styles['Center']))

        elements.append(Spacer(1, 30))
        elements.append(Spacer(1, 30))
        # elements.append(Spacer(1, 30))
        
        elements.append(Paragraph("VALDEZ Y ANDRADE SOLUCIONES S.A.S", styles['Center']))
        elements.append(Paragraph("NIT: 901.272.598-7", styles['Center']))
        
        
        # Pie de página
        # elements.append(Spacer(1,30))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("CRA. 60A # 29 - 47 BARRIO LOS ANGELES", styles['Center']))
        
        # Generar PDF
        doc.build(elements)
        return response