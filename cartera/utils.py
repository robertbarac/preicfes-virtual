from datetime import timedelta, date
import calendar
from dateutil.relativedelta import relativedelta

def calcular_fecha_inicio_inteligente(fecha_base, frecuencia):
    """
    Calcula una fecha de inicio inteligente para la primera cuota,
    asegurando que haya un mínimo de días desde el pago inicial.
    """
    MIN_DIAS_DIFERENCIA = 10

    # Lógica para Quincenal
    if frecuencia == 'quincenal':
        posibles_fechas = []
        # Generar candidatos para los próximos 2 meses
        for i in range(2):
            mes_siguiente = fecha_base + relativedelta(months=i)
            dia_15 = date(mes_siguiente.year, mes_siguiente.month, 15)
            ultimo_dia = date(mes_siguiente.year, mes_siguiente.month, calendar.monthrange(mes_siguiente.year, mes_siguiente.month)[1])
            if dia_15 > fecha_base: posibles_fechas.append(dia_15)
            if ultimo_dia > fecha_base: posibles_fechas.append(ultimo_dia)

        for fecha_candidata in sorted(list(set(posibles_fechas))):
            if (fecha_candidata - fecha_base).days >= MIN_DIAS_DIFERENCIA:
                return fecha_candidata

    # Lógica para Mensual
    elif frecuencia == 'mensual':
        fecha_candidata = fecha_base + relativedelta(months=1)
        if fecha_base.day > 20: # Si se inscribe a final de mes
             ultimo_dia_siguiente_mes = calendar.monthrange(fecha_candidata.year, fecha_candidata.month)[1]
             fecha_candidata = date(fecha_candidata.year, fecha_candidata.month, ultimo_dia_siguiente_mes)
        
        while (fecha_candidata - fecha_base).days < MIN_DIAS_DIFERENCIA:
            fecha_candidata += relativedelta(months=1)
        return fecha_candidata

    # Lógica para Semanal (pago los viernes)
    elif frecuencia == 'semanal':
        dias_para_viernes = (4 - fecha_base.weekday() + 7) % 7
        fecha_candidata = fecha_base + timedelta(days=dias_para_viernes)
        if fecha_candidata == fecha_base: # si hoy es viernes, la próxima es la otra semana
            fecha_candidata += timedelta(weeks=1)

        if (fecha_candidata - fecha_base).days < MIN_DIAS_DIFERENCIA:
            fecha_candidata += timedelta(weeks=1)
        return fecha_candidata

    return fecha_base + timedelta(days=MIN_DIAS_DIFERENCIA) # Fallback por si algo falla


def generar_fechas_pago(fecha_inicio, fecha_fin, frecuencia_pago, valor_total):
    """
    Genera fechas de pago y el valor de cada cuota basadas en la frecuencia.
    Los valores de las cuotas serán múltiplos de 1000.

    Parámetros:
    - fecha_inicio: Fecha de inicio del periodo de pago (datetime.date).
    - fecha_fin: Fecha de finalización del periodo de pago (datetime.date).
    - frecuencia_pago: 'semanal', 'quincenal', o 'mensual'.
    - valor_total: Valor total de la deuda.

    Retorna:
    - Lista de tuplas (fecha_pago, valor_cuota).
    """
    fechas_temp = []
    fecha_actual = fecha_inicio

    if frecuencia_pago == 'semanal':
        # Para pago semanal, el día de pago será el viernes de cada semana.
        dia_pago = 4  # 0=Lunes, 4=Viernes
        
        # Ajustar la fecha_actual al primer día de pago
        dias_para_viernes = (dia_pago - fecha_actual.weekday() + 7) % 7
        fecha_actual = fecha_actual + timedelta(days=dias_para_viernes)
        
        while fecha_actual <= fecha_fin:
            fechas_temp.append(fecha_actual)
            fecha_actual += timedelta(weeks=1)

    elif frecuencia_pago == 'quincenal':
        # Pagos los días 15 y último día de cada mes.
        while fecha_actual <= fecha_fin:
            # Primer pago del mes (día 15)
            dia_15 = date(fecha_actual.year, fecha_actual.month, 15)
            if fecha_inicio <= dia_15 <= fecha_fin:
                fechas_temp.append(dia_15)
            
            # Segundo pago del mes (último día)
            ultimo_dia_mes = calendar.monthrange(fecha_actual.year, fecha_actual.month)[1]
            fecha_ultimo_dia = date(fecha_actual.year, fecha_actual.month, ultimo_dia_mes)
            if fecha_inicio <= fecha_ultimo_dia <= fecha_fin and fecha_ultimo_dia > dia_15:
                fechas_temp.append(fecha_ultimo_dia)
            
            # Avanzar al primer día del siguiente mes
            if fecha_actual.month == 12:
                fecha_actual = date(fecha_actual.year + 1, 1, 1)
            else:
                fecha_actual = date(fecha_actual.year, fecha_actual.month + 1, 1)

    elif frecuencia_pago == 'mensual':
        # Pagos en el día del mes correspondiente a la fecha de inicio.
        dia_pago = fecha_inicio.day
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            fechas_temp.append(fecha_actual)
            # Avanzar al siguiente mes
            if fecha_actual.month == 12:
                fecha_actual = date(fecha_actual.year + 1, 1, dia_pago)
            else:
                try:
                    fecha_actual = date(fecha_actual.year, fecha_actual.month + 1, dia_pago)
                except ValueError: # Día no existe en el siguiente mes (ej. 31 de febrero)
                    ultimo_dia_siguiente_mes = calendar.monthrange(fecha_actual.year, fecha_actual.month + 1)[1]
                    fecha_actual = date(fecha_actual.year, fecha_actual.month + 1, ultimo_dia_siguiente_mes)

    # Eliminar duplicados y ordenar
    fechas_pago_unicas = sorted(list(set(fechas_temp)))
    
    # Calcular el valor de cada cuota
    num_cuotas = len(fechas_pago_unicas)
    if num_cuotas == 0:
        return []

    valor_cuota_base = valor_total / num_cuotas
    # Redondear al múltiplo de 1000 más cercano
    valor_cuota_redondeado = round(valor_cuota_base / 1000) * 1000
    
    cuotas = []
    total_asignado = 0
    
    for i, fecha in enumerate(fechas_pago_unicas):
        if i < num_cuotas - 1:
            cuotas.append((fecha, valor_cuota_redondeado))
            total_asignado += valor_cuota_redondeado
        else:
            # La última cuota ajusta la diferencia
            valor_ultima_cuota = valor_total - total_asignado
            cuotas.append((fecha, valor_ultima_cuota))
            
    return cuotas
