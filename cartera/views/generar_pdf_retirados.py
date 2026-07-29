from django.http import HttpResponse
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from academico.models import Alumno
from django.utils import timezone

def generar_pdf_retirados_view(request):
    # Obtener los alumnos retirados con exactamente la misma lógica de filtrado que la vista de lista
    queryset = Alumno.objects.filter(estado='retirado', fecha_retiro__isnull=False)
    
    # Recuperar parámetros de filtrado de la URL
    departamento_id = request.GET.get('departamento')
    municipio_id = request.GET.get('municipio')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    tipo_programa = request.GET.get('tipo_programa')
    
    # Aplicar filtros según el rol del usuario
    user = request.user
    if user.is_superuser:
        if departamento_id:
            queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento_id=departamento_id)
        if municipio_id:
            queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
    elif user.groups.filter(name__in=['CoordinadorDepartamental', 'Auxiliar']).exists():
        if hasattr(user, 'departamento') and user.departamento:
            queryset = queryset.filter(grupo_actual__salon__sede__municipio__departamento=user.departamento)
            if municipio_id:
                queryset = queryset.filter(grupo_actual__salon__sede__municipio_id=municipio_id)
        else:
            queryset = queryset.none()
    else:  # Otros roles de staff
        if hasattr(user, 'municipio') and user.municipio:
            queryset = queryset.filter(grupo_actual__salon__sede__municipio=user.municipio)
        else:
            queryset = queryset.none()
    
    # Filtros adicionales (igual que en la vista principal)
    if mes:
        try:
            mes_int = int(mes)
            queryset = queryset.filter(fecha_retiro__month=mes_int)
        except (ValueError, TypeError):
            pass
    
    if anio:
        try:
            anio_int = int(anio)
            queryset = queryset.filter(fecha_retiro__year=anio_int)
        except (ValueError, TypeError):
            pass
    
    if tipo_programa:
        queryset = queryset.filter(tipo_programa=tipo_programa)

    alumnos_retirados = queryset.select_related(
        'municipio', 'grupo_actual', 'grupo_actual__salon__sede__municipio'
    ).order_by('primer_apellido', 'segundo_apellido', 'nombres')

    # Configurar la respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    hoy = timezone.localtime(timezone.now())
    fecha_str_filename = hoy.strftime('%Y-%m-%d')
    filename = f"informe_retirados_{fecha_str_filename}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    # Crear el documento PDF
    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()

    # Fecha y Título
    fecha_str_display = hoy.strftime('%d de %B de %Y')
    elements.append(Paragraph(fecha_str_display, styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("Listado de Alumnos Retirados", styles['h1']))

    # Agregar filtros aplicados al título
    filtros_aplicados = []
    if departamento_id:
        try:
            from ubicaciones.models import Departamento
            depto = Departamento.objects.get(id=departamento_id)
            filtros_aplicados.append(f"Departamento: {depto.nombre}")
        except Exception:
            pass
    
    if municipio_id:
        try:
            from ubicaciones.models import Municipio
            muni = Municipio.objects.get(id=municipio_id)
            filtros_aplicados.append(f"Municipio: {muni.nombre}")
        except Exception:
            pass
    
    if mes:
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        try:
            mes_int = int(mes)
            if 1 <= mes_int <= 12:
                filtros_aplicados.append(f"Mes: {meses[mes_int]}")
        except (ValueError, TypeError):
            pass
    
    if anio:
        filtros_aplicados.append(f"Año: {anio}")
    
    if tipo_programa:
        programas = dict(Alumno.TIPO_PROGRAMA)
        filtros_aplicados.append(f"Programa: {programas.get(tipo_programa, tipo_programa)}")
    
    if filtros_aplicados:
        elements.append(Paragraph("Filtros aplicados: " + ", ".join(filtros_aplicados), styles['Normal']))
        elements.append(Spacer(1, 0.2 * inch))
    
    # Datos de la tabla
    data = [[
        'Nombre Completo',
        'Tipo Programa',
        'Municipio',
        'Grupo',
        'Fecha Retiro',
        'Teléfono',
        'Saldo Pendiente'
    ]]

    for alumno in alumnos_retirados:
        nombre_completo = f"{alumno.nombres} {alumno.primer_apellido} {alumno.segundo_apellido or ''}".strip()
        saldo_pendiente = getattr(alumno.deuda, 'saldo_pendiente', 0) if hasattr(alumno, 'deuda') and alumno.deuda else 0
        
        # Obtener el nombre del tipo de programa
        programas = dict(Alumno.TIPO_PROGRAMA)
        tipo_programa_nombre = programas.get(alumno.tipo_programa, 'No definido')
        
        data.append([
            nombre_completo,
            tipo_programa_nombre,
            alumno.municipio.nombre if alumno.municipio else 'N/A',
            alumno.grupo_actual.codigo if alumno.grupo_actual else 'N/A',
            alumno.fecha_retiro.strftime('%d/%m/%Y') if alumno.fecha_retiro else 'N/A',
            alumno.celular or 'N/A',
            f"${saldo_pendiente:,.0f}".replace(',', '.')
        ])

    # Estilo de la tabla
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])

    # Crear y estilizar la tabla
    table = Table(data)
    table.setStyle(style)
    elements.append(table)

    # Calcular totales
    total_retirados = alumnos_retirados.count()
    total_saldo_pendiente = sum(getattr(alumno.deuda, 'saldo_pendiente', 0) for alumno in alumnos_retirados if hasattr(alumno, 'deuda') and alumno.deuda)

    # Añadir un espacio
    elements.append(Spacer(1, 0.2 * inch))

    # Añadir totales al PDF
    styles = getSampleStyleSheet()
    total_retirados_text = f"<b>Total de alumnos retirados:</b> {total_retirados}"
    total_saldo_text = f"<b>Saldo pendiente total:</b> ${total_saldo_pendiente:,.0f}".replace(',', '.')

    elements.append(Paragraph(total_retirados_text, styles['Normal']))
    elements.append(Paragraph(total_saldo_text, styles['Normal']))

    doc.build(elements)

    return response
