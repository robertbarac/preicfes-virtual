from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from academico.models import Alumno
from cartera.models import Deuda, Cuota
from cartera.forms import GenerarCuotasForm
from cartera.utils import generar_fechas_pago, calcular_fecha_inicio_inteligente

@login_required
@permission_required('cartera.add_cuota', raise_exception=True)
def generar_cuotas_view(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    try:
        deuda = Deuda.objects.get(alumno=alumno, estado='emitida')
    except Deuda.DoesNotExist:
        messages.error(request, 'El alumno no tiene una deuda activa.')
        return redirect('alumno_detail', pk=alumno.id)

    if Cuota.objects.filter(deuda=deuda).exists():
        messages.warning(request, 'Este alumno ya tiene cuotas generadas.')
        return redirect('alumno_detail', pk=alumno.id)

    if request.method == 'POST':
        form = GenerarCuotasForm(request.POST)
        if form.is_valid():
            # 1. Extraer datos del formulario
            frecuencia = alumno.frecuencia_pago
            monto_inicial = form.cleaned_data['monto_cuota_inicial']
            fecha_pago_inicial = form.cleaned_data['fecha_pago_inicial']
            metodo_pago_inicial = form.cleaned_data['metodo_pago_inicial']

            # 2. Crear y registrar la cuota inicial como pagada
            from cartera.utils_audit import registrar_log_audit, ADDITION
            c_inicial = Cuota.objects.create(
                deuda=deuda,
                monto=monto_inicial,
                monto_abonado=monto_inicial,
                fecha_vencimiento=fecha_pago_inicial,
                fecha_pago=fecha_pago_inicial,
                estado='pagada',
                metodo_pago=metodo_pago_inicial
            )
            registrar_log_audit(request.user, c_inicial, ADDITION, f"Cuota inicial de ${monto_inicial} generada y registrada como pagada desde el sitio web.")
            # La lógica del modelo Cuota.save() ya actualiza el saldo de la deuda.

            # 3. Preparar para generar cuotas restantes
            deuda.refresh_from_db() # Recargar la deuda para obtener el saldo pendiente actualizado
            valor_restante = deuda.saldo_pendiente

            if valor_restante <= 0:
                deuda.cuotas_generadas = True
                deuda.save()
                messages.success(request, 'La deuda ha sido saldada con el pago inicial. No se generaron cuotas adicionales.')
                return redirect('alumno_detail', pk=alumno.id)

            # 4. Calcular la fecha de inicio inteligente para la primera cuota masiva
            fecha_inicio_inteligente = calcular_fecha_inicio_inteligente(fecha_pago_inicial, frecuencia)
            
            fecha_fin = alumno.fecha_culminacion or (fecha_inicio_inteligente + timezone.timedelta(days=365))

            # 5. Generar las fechas y montos para las cuotas restantes
            cuotas_a_crear = generar_fechas_pago(fecha_inicio_inteligente, fecha_fin, frecuencia, valor_restante)

            if not cuotas_a_crear:
                deuda.cuotas_generadas = True # Se generó la cuota inicial
                deuda.save()
                messages.warning(request, f'Cuota inicial de {monto_inicial} registrada, pero no se pudieron generar cuotas restantes. El valor restante podría ser muy bajo o las fechas no son válidas.')
                return redirect('alumno_detail', pk=alumno.id) # Redirigir a detalle, ya que la cuota inicial sí se creó

            # 6. Crear las cuotas restantes en la base de datos
            for fecha_vencimiento, monto in cuotas_a_crear:
                c_nueva = Cuota.objects.create(
                    deuda=deuda,
                    monto=monto,
                    fecha_vencimiento=fecha_vencimiento,
                    estado='emitida'
                )
                registrar_log_audit(request.user, c_nueva, ADDITION, f"Cuota masiva de ${monto} generada desde el sitio web.")
            
            deuda.cuotas_generadas = True
            deuda.save()

            messages.success(request, f'Cuota inicial registrada. Se generaron {len(cuotas_a_crear)} cuotas adicionales exitosamente.')
            return redirect('alumno_detail', pk=alumno.id)
    else:
        form = GenerarCuotasForm()

    context = {
        'form': form,
        'alumno': alumno,
        'deuda': deuda
    }
    return render(request, 'cartera/generar_cuotas_form.html', context)
