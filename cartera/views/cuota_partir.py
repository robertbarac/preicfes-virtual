# cartera/views/cuota_partir.py

from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from cartera.models import Cuota
from cartera.utils_audit import registrar_log_audit, ADDITION, DELETION


class CuotaPartirView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Permite partir una cuota (emitida o vencida) en dos cuotas pagadas
    con diferentes métodos de pago (ej. Efectivo y Transferencia/Nequi),
    conservando la fecha de vencimiento y recalculando la deuda.
    """
    template_name = 'cartera/cuota_partir.html'

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.username == 'vvgomez':
            return True
        if user.is_staff or user.groups.filter(name__in=['SecretariaCartera', 'CoordinadorDepartamental', 'Auxiliar']).exists():
            return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permisos para partir cuotas.")
        return redirect('alumnos_list')

    def get_cuota(self, pk):
        return get_object_or_404(
            Cuota.objects.select_related('deuda', 'deuda__alumno'),
            pk=pk
        )

    def get(self, request, pk):
        cuota = self.get_cuota(pk)
        alumno = cuota.deuda.alumno
        redirect_url = f"{reverse('alumno_detail', kwargs={'pk': alumno.pk})}#tab-historial-pagos"

        if cuota.estado not in ['emitida', 'vencida']:
            messages.error(request, f"La cuota #{cuota.id} no se puede partir porque se encuentra en estado '{cuota.get_estado_display()}'. Solo se pueden partir cuotas emitidas o vencidas.")
            return redirect(redirect_url)

        context = {
            'cuota': cuota,
            'alumno': alumno,
            'today': timezone.localtime(timezone.now()).date(),
            'metodos_pago': Cuota.METODO_PAGO,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        cuota = self.get_cuota(pk)
        alumno = cuota.deuda.alumno
        redirect_url = f"{reverse('alumno_detail', kwargs={'pk': alumno.pk})}#tab-historial-pagos"

        if cuota.estado not in ['emitida', 'vencida']:
            messages.error(request, f"La cuota #{cuota.id} no se puede partir porque se encuentra en estado '{cuota.get_estado_display()}'. Solo se pueden partir cuotas emitidas o vencidas.")
            return redirect(redirect_url)

        # 1. Parsear montos
        monto_1_raw = request.POST.get('monto_1', '').strip().replace(',', '.')
        monto_2_raw = request.POST.get('monto_2', '').strip().replace(',', '.')

        try:
            monto_1 = Decimal(monto_1_raw)
            monto_2 = Decimal(monto_2_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Los montos de las cuotas deben ser valores numéricos válidos.")
            return redirect(redirect_url)

        if monto_1 <= 0 or monto_2 <= 0:
            messages.error(request, "Los montos de ambas partes deben ser mayores a $0.")
            return redirect(redirect_url)

        # 2. Verificar que la suma de los 2 montos sea exactamente igual al monto original
        monto_original = cuota.monto
        if (monto_1 + monto_2) != monto_original:
            messages.error(
                request,
                f"La suma de los montos ingresados (${monto_1:,.2f} + ${monto_2:,.2f} = ${(monto_1 + monto_2):,.2f}) "
                f"no coincide con el valor total de la cuota original (${monto_original:,.2f})."
            )
            return redirect(redirect_url)

        # 3. Validar métodos de pago
        metodo_pago_1 = request.POST.get('metodo_pago_1', '').strip()
        metodo_pago_2 = request.POST.get('metodo_pago_2', '').strip()
        metodos_validos = [m[0] for m in Cuota.METODO_PAGO]

        if metodo_pago_1 not in metodos_validos or metodo_pago_2 not in metodos_validos:
            messages.error(request, "Debes seleccionar un método de pago válido para ambas cuotas.")
            return redirect(redirect_url)

        # 4. Validar fecha de pago
        fecha_pago_raw = request.POST.get('fecha_pago', '').strip()
        today = timezone.localtime(timezone.now()).date()

        if fecha_pago_raw:
            try:
                fecha_pago = datetime.strptime(fecha_pago_raw, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "La fecha de pago ingresada no es válida.")
                return redirect(redirect_url)
        else:
            fecha_pago = today

        if fecha_pago > today:
            messages.error(request, "La fecha de pago no puede ser una fecha futura.")
            return redirect(redirect_url)

        soporte_1 = request.FILES.get('soporte_pago_1')
        soporte_2 = request.FILES.get('soporte_pago_2')

        # 5. Ejecutar la división en una transacción atómica
        with transaction.atomic():
            deuda = cuota.deuda
            fecha_vencimiento = cuota.fecha_vencimiento
            username = request.user.username or 'sistema'
            now_dt = timezone.now()

            # Guardar lista de acuerdos para no perderlos si existen
            acuerdos = list(cuota.acuerdos.all())

            # Crear Cuota 1 (pagada en su totalidad por monto_1)
            cuota_1 = Cuota(
                deuda=deuda,
                monto=monto_1,
                monto_abonado=monto_1,
                fecha_vencimiento=fecha_vencimiento,
                fecha_pago=fecha_pago,
                estado='pagada',
                metodo_pago=metodo_pago_1,
                editado_por=username,
                fecha_edicion=now_dt
            )
            if soporte_1:
                cuota_1.soporte_pago = soporte_1
            cuota_1.save(run_logic=False)

            # Crear Cuota 2 (pagada en su totalidad por monto_2)
            cuota_2 = Cuota(
                deuda=deuda,
                monto=monto_2,
                monto_abonado=monto_2,
                fecha_vencimiento=fecha_vencimiento,
                fecha_pago=fecha_pago,
                estado='pagada',
                metodo_pago=metodo_pago_2,
                editado_por=username,
                fecha_edicion=now_dt
            )
            if soporte_2:
                cuota_2.soporte_pago = soporte_2
            cuota_2.save(run_logic=False)

            # Transferir y cumplir acuerdos si existían en la cuota original
            for acuerdo in acuerdos:
                acuerdo.cuota = cuota_1
                acuerdo.estado = 'cumplido'
                acuerdo.save()

            # Registrar auditoría en LogEntry
            registrar_log_audit(
                request.user,
                cuota_1,
                ADDITION,
                f"Cuota creada por división de cuota #{cuota.id} (${monto_1:,.2f} vía {metodo_pago_1})"
            )
            registrar_log_audit(
                request.user,
                cuota_2,
                ADDITION,
                f"Cuota creada por división de cuota #{cuota.id} (${monto_2:,.2f} vía {metodo_pago_2})"
            )
            registrar_log_audit(
                request.user,
                cuota,
                DELETION,
                f"Cuota original #{cuota.id} (${monto_original:,.2f}) eliminada tras partirse en cuotas #{cuota_1.id} y #{cuota_2.id}"
            )

            # Eliminar la cuota original
            cuota.delete()

            # Recalcular saldo y estado de la deuda completa
            deuda.actualizar_saldo_y_estado()

        messages.success(
            request,
            f"✅ ¡Cuota de ${monto_original:,.0f} partida exitosamente! "
            f"Se crearon dos cuotas pagadas: una por ${monto_1:,.0f} ({metodo_pago_1.title()}) "
            f"y otra por ${monto_2:,.0f} ({metodo_pago_2.title()})."
        )
        return redirect(redirect_url)
