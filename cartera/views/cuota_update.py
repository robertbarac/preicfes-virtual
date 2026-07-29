# Django imports
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import F
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic.edit import UpdateView
from datetime import timedelta

# Local imports
from cartera.forms import CuotaUpdateForm
from cartera.models import Cuota

class CuotaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Cuota
    form_class = CuotaUpdateForm
    template_name = 'cartera/cuota_update_form.html'
    
    def test_func(self):
        # vvgomez tiene acceso total para editar cualquier cuota.
        if self.request.user.username == 'vvgomez':
            return True
        
        # Para otros usuarios, permitir solo si son staff/superuser Y la cuota no tiene abonos.
        cuota = self.get_object()
        user_is_authorized = self.request.user.is_staff or self.request.user.is_superuser
        cuota_is_editable = cuota.monto_abonado == 0
        return user_is_authorized and cuota_is_editable

    def handle_no_permission(self):
        return redirect('alumnos_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuota = self.get_object()
        context['alumno'] = cuota.deuda.alumno
        return context

    def form_valid(self, form):
        from django.utils import timezone

        # 1. OBTENER DATOS DEL FORMULARIO Y ESTADO ORIGINAL
        # Obtenemos la instancia con los datos nuevos del form, pero sin guardar aún.
        cuota_actual = form.save(commit=False)
        # Registrar quién editó y cuándo
        cuota_actual.editado_por = self.request.user.username
        cuota_actual.fecha_edicion = timezone.localtime(timezone.now())
        # Obtenemos la cuota original de la BD para comparar.
        cuota_original = Cuota.objects.get(pk=cuota_actual.pk)

        # Calculamos la diferencia para saber si es un pago nuevo.
        abono_transaccion = cuota_actual.monto_abonado - cuota_original.monto_abonado

        # Guardamos la cuota con TODOS sus nuevos datos (fecha, método, etc.)
        cuota_actual.save()
        from cartera.utils_audit import registrar_log_audit, CHANGE
        registrar_log_audit(
            self.request.user, 
            cuota_actual, 
            CHANGE, 
            f"Cuota de ${cuota_actual.monto} editada. Abonado: ${cuota_actual.monto_abonado} (Abono transacción: ${abono_transaccion}). Estado: {cuota_actual.estado}."
        )

        if abono_transaccion <= 0:
            messages.info(self.request, "Cambios guardados, pero no se registró un nuevo abono.")
            return redirect(self.get_success_url())

        # Si hubo un abono, continuamos con la lógica de pagos.
        messages.success(self.request, f"Se registró un pago de ${abono_transaccion:,.2f}.")
        cuota_actual.refresh_from_db()

        # 3. DETERMINAR LÓGICA: PAGO PARCIAL O EXCEDENTE
        # El excedente es la diferencia entre lo que se abonó y el monto que se debía.
        excedente = cuota_actual.monto_abonado - cuota_actual.monto

        if excedente > 0:
            # --- LÓGICA DE EXCEDENTE: VACIADO DE CUOTAS FUTURAS ---
            cuotas_siguientes = Cuota.objects.filter(
                deuda=cuota_actual.deuda,
                fecha_vencimiento__gt=cuota_actual.fecha_vencimiento
            ).order_by('fecha_vencimiento')

            for cuota_futura in cuotas_siguientes:
                if excedente <= 0: break
                
                monto_a_reducir = min(excedente, cuota_futura.monto)
                cuota_futura.monto -= monto_a_reducir
                excedente -= monto_a_reducir
                
                # Si la cuota queda en 0, se marca como pagada.
                if cuota_futura.monto == 0:
                    cuota_futura.estado = 'pagada'
                
                cuota_futura.save()
                messages.info(self.request, f"Excedente de ${monto_a_reducir:,.2f} redujo el monto de la cuota del {cuota_futura.fecha_vencimiento.strftime('%d/%m/%Y')}.")

            if excedente > 0:
                # Si aún queda excedente, se crea un saldo a favor.
                ultima_fecha = cuota_actual.deuda.cuotas.latest('fecha_vencimiento').fecha_vencimiento
                Cuota.objects.create(
                    deuda=cuota_actual.deuda, monto=0, monto_abonado=-excedente,
                    fecha_vencimiento=ultima_fecha + timedelta(days=30), concepto="Saldo a favor", estado='pagada'
                )
                messages.warning(self.request, f"¡Saldo a favor! Se registró un crédito de ${excedente:,.2f}.")

        elif cuota_actual.estado == 'pagada_parcial':
            # --- LÓGICA DE PAGO PARCIAL: REFINANCIACIÓN ---
            saldo_restante = cuota_actual.monto - cuota_actual.monto_abonado
            if saldo_restante > 0:
                siguiente_cuota = Cuota.objects.filter(
                    deuda=cuota_actual.deuda, fecha_vencimiento__gt=cuota_actual.fecha_vencimiento
                ).order_by('fecha_vencimiento').first()

                if siguiente_cuota:
                    siguiente_cuota.monto += saldo_restante
                    siguiente_cuota.save()
                    messages.info(self.request, f"Saldo de ${saldo_restante:,.2f} fue transferido a la próxima cuota.")
                else:
                    Cuota.objects.create(
                        deuda=cuota_actual.deuda, monto=saldo_restante,
                        fecha_vencimiento=cuota_actual.fecha_vencimiento + timedelta(days=30),
                        concepto="Saldo de cuota anterior", estado='emitida'
                    )
                    messages.warning(self.request, f"Se creó una nueva cuota por ${saldo_restante:,.2f}.")
                
                # La cuota original ya está como 'pagada_parcial', no se cambia su estado aquí.

        # 4. ACTUALIZACIÓN FINAL
        cuota_actual.deuda.actualizar_saldo_y_estado()
        return redirect(self.get_success_url())

    def get_success_url(self):
        cuota = self.get_object()
        return reverse('alumno_detail', kwargs={'pk': cuota.deuda.alumno.id})