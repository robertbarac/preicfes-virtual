    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar el mensaje preformateado y días restantes a cada cuota
        for cuota in context['cuotas']:
            alumno = cuota.deuda.alumno
            if cuota.estado == "emitida":
                # Renderizar el mensaje con los datos actuales
                message_context = {
                    'nombres': alumno.nombres,
                    'primer_apellido': alumno.primer_apellido,
                    'fecha_vencimiento': cuota.fecha_vencimiento,
                    'dias_restantes': (cuota.fecha_vencimiento - timezone.localtime(timezone.now()).date()).days,
                    'monto': cuota.monto
                }
                
                # Renderizar el template y codificar para URL
                cuota.whatsapp_message = render_to_string(
                    'cartera/proximo_pago_template.txt',
                    message_context
                ).replace('\n', '%0A').replace(' ', '%20')
            
            elif cuota.estado == "vencida":
                cuota.dias_atraso = (timezone.localtime(timezone.now()).date() - cuota.fecha_vencimiento).days
                # Renderizar el mensaje con los datos actuales
                message_context = {
                    'nombres': alumno.nombres,
                    'primer_apellido': alumno.primer_apellido,
                    'fecha_vencimiento': cuota.fecha_vencimiento,
                    'dias_atraso': cuota.dias_atraso,
                    'monto': cuota.monto,
                    'monto_abonado': cuota.monto_abonado,
                    'saldo_pendiente': cuota.deuda.saldo_pendiente
                }
                
                # Renderizar el template y codificar para URL
                cuota.whatsapp_message = render_to_string(
                    'cartera/whatsapp_message_template.txt',
                    message_context
                ).replace('\n', '%0A').replace(' ', '%20')