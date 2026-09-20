from django.http import HttpResponse
from django.shortcuts import redirect
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.utils import timezone
from django.utils.formats import date_format


def generar_pdf_informe(request):
    if request.method != 'POST':
        return redirect('cartera:informe_diario')

    # Función robusta para formatear valores como moneda con separadores de miles (puntos)
    def format_currency(value):
        if value is None:
            return "$0"
        s = str(value).strip().replace('$', '').replace(' ', '')
        if not s:
            return "$0"
        try:
            is_negative = s.startswith('-')
            if is_negative:
                s = s[1:]
            if ',' in s and '.' in s:
                if s.rfind(',') > s.rfind('.'):
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            elif ',' in s:
                parts = s.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    s = parts[0]
                else:
                    s = s.replace(',', '')
            elif '.' in s:
                parts = s.split('.')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    s = parts[0]
                else:
                    s = s.replace('.', '')
            num = int(round(float(s)))
            formatted = f"{num:,}".replace(',', '.')
            prefix = "-$" if is_negative else "$"
            return f"{prefix}{formatted}"
        except Exception:
            return f"${value}"

    # Obtener datos del formulario
    efectivo_sedes = request.POST.get('efectivo_sedes', '0')
    
    # Configurar el PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="informe_diario.pdf"'
    
    # Crear el canvas
    p = canvas.Canvas(response, pagesize=letter)
    
    # Obtener fecha formateada (los módulos ya están importados globalmente)
    hoy = timezone.localtime(timezone.now()).date()
    fecha_str = date_format(hoy, "l, j \d\e F \d\e Y").capitalize()
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "Informe Diario de Cartera")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, fecha_str)
    
    # Datos de recaudación
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 700, "Recaudación del Día")
    p.setFont("Helvetica", 12)
    
    y_position = 680
    datos = [
        ("Efectivo:", format_currency(request.POST.get('recaudo_efectivo', '0'))),
        ("Transferencia:", format_currency(request.POST.get('recaudo_transferencia', '0'))),
        ("Datáfono:", format_currency(request.POST.get('recaudo_datáfono', '0'))),
        ("No especificado:", format_currency(request.POST.get('recaudo_no_especificado', '0'))),
        ("Total Recaudado:", format_currency(request.POST.get('total_recaudado', '0'))),
        ("Efectivo en sedes:", format_currency(efectivo_sedes))
    ]
    
    for label, value in datos:
        p.drawString(100, y_position, f"{label} {value}")
        y_position -= 20
    
    # Objetivos
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y_position - 20, "Objetivos del Mes")
    p.setFont("Helvetica", 12)
    y_position -= 40
    
    porcentaje_raw = str(request.POST.get('porcentaje_cumplimiento', '0')).strip().replace('%', '').replace(',', '.')
    try:
        porcentaje_val = float(porcentaje_raw)
        porcentaje_str = f"{porcentaje_val:.1f}%".replace('.', ',')
    except ValueError:
        porcentaje_str = f"{porcentaje_raw}%"

    objetivos = [
        ("Objetivo:", format_currency(request.POST.get('objetivo_mes', '0'))),
        ('Recaudado del mes:', format_currency(request.POST.get('recaudado_mes', '0'))),
        ("% Cumplimiento:", porcentaje_str)
    ]
    
    # Dibujar tabla de objetivos
    for label, value in objetivos:
        p.drawString(100, y_position, f"{label} {value}")
        y_position -= 20
    
    # Reporte de cartera
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y_position - 20, "Reporte de Cartera")
    p.setFont("Helvetica", 12)
    y_position -= 40
    
    cartera = [
        ("Valor Cartera:", format_currency(request.POST.get('valor_cartera', '0'))),
        ("Cobrado:", format_currency(request.POST.get('cobrado', '0'))),
        ("Falta por Cobrar:", format_currency(request.POST.get('falta_cobrar', '0')))
    ]
    
    for label, value in cartera:
        p.drawString(100, y_position, f"{label} {value}")
        y_position -= 20
    
    p.showPage()
    p.save()
    
    return response