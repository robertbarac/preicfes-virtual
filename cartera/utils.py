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


def evaluar_bloqueo_cartera(alumno=None, user=None, identificacion=None):
    """
    Evalúa si un estudiante tiene bloqueo de resultados de simulacros por cartera.
    Condición 1: Tiene al menos una cuota vencida sin pagar (estado 'vencida' con saldo > 0,
                 o fecha_vencimiento < hoy sin abonos).
    Condición 2: No tiene vencidas sin pagar, pero tiene cuotas pagadas parciales cuya
                 fecha_vencimiento < hoy (ya vencidas) y la suma de montos de cuotas causadas
                 (fecha_vencimiento < hoy) pagadas/parciales > suma de sus montos abonados.
    Nota: Los abonos parciales en cuotas futuras (fecha_vencimiento >= hoy) NO bloquean,
          permitiendo que los estudiantes que adelantan pagos puedan ver sus resultados.
    """
    import re
    from django.utils import timezone
    from django.db.models import Q
    from cartera.models import Deuda

    resultado = {
        'bloquear': False,
        'motivo': None,
        'cuotas_afectadas': [],
        'deuda': None,
        'cuotas': [],
        'total_abonado': 0,
        'tiene_cuotas_vencidas': False,
        'suma_montos_pagadas_o_parciales': 0,
        'suma_abonados_pagadas_o_parciales': 0,
    }

    deuda = None
    if alumno and hasattr(alumno, 'deuda'):
        try:
            deuda = alumno.deuda
        except Exception:
            deuda = None

    if not deuda:
        doc_target = (
            getattr(alumno, 'identificacion', None) or 
            (getattr(user, 'numero_documento', None) if user else None) or
            identificacion
        )
        if doc_target:
            clean_doc = re.sub(r'[^0-9a-zA-Z]', '', str(doc_target))
            deuda = Deuda.objects.filter(
                Q(alumno__identificacion__iexact=doc_target) |
                Q(alumno__identificacion__iexact=clean_doc)
            ).select_related('alumno').first()

    if not deuda and user:
        deuda = Deuda.objects.filter(alumno__usuario=user).select_related('alumno').first()

    resultado['deuda'] = deuda
    if not deuda:
        return resultado

    try:
        cuotas = list(deuda.cuotas.all().order_by('fecha_vencimiento'))
        today = timezone.localtime(timezone.now()).date()
        total_abonado = 0

        for idx, cuota in enumerate(cuotas, 1):
            cuota.numero_cuota = idx
            cuota.saldo_restante = max(0, cuota.monto - cuota.monto_abonado)

            if cuota.estado == 'pagada' or cuota.monto_abonado >= cuota.monto:
                cuota.estado_calculado = "Pagada"
                cuota.badge_color = "bg-emerald-100 text-emerald-800 border-emerald-200"
            elif cuota.estado == 'pagada_parcial' or cuota.monto_abonado > 0:
                if today > cuota.fecha_vencimiento:
                    cuota.estado_calculado = "Parcial (Vencida)"
                    cuota.badge_color = "bg-rose-100 text-rose-800 border-rose-200"
                else:
                    cuota.estado_calculado = "Abono Anticipado"
                    cuota.badge_color = "bg-teal-100 text-teal-800 border-teal-200"
            elif cuota.estado == 'vencida' or today > cuota.fecha_vencimiento:
                cuota.estado_calculado = "Vencida"
                cuota.badge_color = "bg-rose-100 text-rose-800 border-rose-200"
            else:
                cuota.estado_calculado = "Al Día"
                cuota.badge_color = "bg-blue-100 text-blue-800 border-blue-200"

            if cuota.estado in ['pagada', 'pagada_parcial'] or cuota.monto_abonado > 0:
                total_abonado += cuota.monto_abonado

        if total_abonado == 0 and deuda.valor_total and deuda.saldo_pendiente is not None:
            total_abonado = max(0, deuda.valor_total - deuda.saldo_pendiente)

        resultado['total_abonado'] = total_abonado
        resultado['cuotas'] = cuotas

        # Si el estudiante ya está a paz y salvo, nunca bloquear
        if deuda.saldo_pendiente is not None and deuda.saldo_pendiente <= 0:
            return resultado

        # Calcular el monto real exigible hasta hoy (evitando doble conteo cuando
        # CuotaUpdateView transfirió el saldo de una cuota parcial a la siguiente,
        # y respetando excedentes ya descontados de cuotas siguientes).
        exigible_a_hoy = 0
        for i, c in enumerate(cuotas):
            if today > c.fecha_vencimiento:
                es_parcial = (c.estado == 'pagada_parcial') or (0 < c.monto_abonado < c.monto)
                siguiente = cuotas[i + 1] if i + 1 < len(cuotas) else None
                if es_parcial and siguiente is not None and today > siguiente.fecha_vencimiento:
                    # El faltante de esta cuota ya fue sumado en `siguiente.monto`
                    exigible_a_hoy += c.monto_abonado
                else:
                    exigible_a_hoy += max(c.monto, c.monto_abonado)

        # Si el total abonado por el alumno (incluyendo adelantos o pagos en cuotas
        # siguientes) ya cubre todo lo exigible hasta hoy, NO debe bloquearse.
        if total_abonado >= exigible_a_hoy:
            for c in cuotas:
                if c.estado_calculado == "Parcial (Vencida)":
                    c.estado_calculado = "Parcial (Cubierta)"
                    c.badge_color = "bg-emerald-100 text-emerald-800 border-emerald-200"
            return resultado

        # Condición 1: Tiene al menos una cuota vencida sin pagar
        cuotas_vencidas = [
            c for c in cuotas 
            if (today > c.fecha_vencimiento and c.saldo_restante > 0 and c.monto_abonado == 0)
            or (c.estado == 'vencida' and c.saldo_restante > 0 and today > c.fecha_vencimiento)
        ]
        tiene_cuotas_vencidas = len(cuotas_vencidas) > 0
        resultado['tiene_cuotas_vencidas'] = tiene_cuotas_vencidas

        # Condición 2: Cuotas pagadas parciales YA VENCIDAS (fecha_vencimiento < hoy)
        cuotas_parciales_vencidas = [
            c for c in cuotas
            if (c.estado == 'pagada_parcial' or (0 < c.monto_abonado < c.monto))
            and today > c.fecha_vencimiento
        ]
        resultado['suma_montos_pagadas_o_parciales'] = exigible_a_hoy
        resultado['suma_abonados_pagadas_o_parciales'] = total_abonado

        if tiene_cuotas_vencidas:
            resultado['bloquear'] = True
            resultado['motivo'] = 'cuotas_vencidas'
            resultado['cuotas_afectadas'] = cuotas_vencidas
        elif cuotas_parciales_vencidas and total_abonado < exigible_a_hoy:
            resultado['bloquear'] = True
            resultado['motivo'] = 'pagadas_parciales'
            resultado['cuotas_afectadas'] = cuotas_parciales_vencidas

    except Exception:
        pass

    return resultado

