from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.db import transaction

from academico.models import Clase, Asistencia, Nota

class RegistroAsistenciaNotaView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Clase
    template_name = 'academico/registro_asistencia_nota.html'
    context_object_name = 'clase'

    def test_func(self):
        user = self.request.user
        clase = self.get_object()
        
        # Si la clase está vista, el profesor no puede acceder más
        if clase.estado == 'vista' and user == clase.profesor:
            return False
            
        # Usar el mismo método que usamos para mostrar el botón
        return clase.puede_registrar_asistencia(user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clase = self.get_object()
        
        # Obtener o crear registros de asistencia y nota para cada alumno
        alumnos_registros = []  # Nota: ahora es con "s" en todos los lugares
        for alumno in clase.grupo.alumnos_actuales.all():
            asistencia, _ = Asistencia.objects.get_or_create(
                alumno=alumno,
                clase=clase,
                defaults={'asistio': False}
            )
            nota, _ = Nota.objects.get_or_create(
                alumno=alumno,
                clase=clase,
                defaults={'nota': None}
            )
            # nota.nota = float(nota.nota) if nota.nota is not None else None
            alumnos_registros.append({  # Asegúrate que este nombre coincida con el de la plantilla
                'alumno': alumno,
                'asistencia': asistencia,
                'nota': nota
            })

        context.update({
            'alumnos_registros': alumnos_registros,  # Nombre consistente
            'titulo': f'Registro de Asistencia y Notas - {clase}',
            'puede_marcar_vista': self.request.user.is_superuser or 
                                self.request.user.groups.filter(name='SecretariaAcademica').exists() or 
                                (self.request.user == clase.profesor and clase.estado != 'vista')
        })
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        clase = self.get_object()
        guardar_y_marcar = request.POST.get('guardar_y_marcar', False)
        
        # Verificar permisos usando el mismo método que el modelo
        if not clase.puede_registrar_asistencia(request.user):
            messages.error(request, 'No tiene permiso para registrar asistencia en este momento.')
            return redirect('profesor_clases', profesor_id=request.user.id)
        
        # Procesar cada alumno
        for alumno in clase.grupo.alumnos_actuales.all():
            # Actualizar asistencia
            asistencia = Asistencia.objects.get_or_create(
                alumno=alumno,
                clase=clase,
                defaults={'asistio': False}
            )[0]
            asistencia.asistio = request.POST.get(f'asistencia_{alumno.id}') == 'on'
            asistencia.save()
            
            # Actualizar nota
            nota = Nota.objects.get_or_create(
                alumno=alumno,
                clase=clase,
                defaults={'nota': None}
            )[0]
            nota_valor = request.POST.get(f'nota_{alumno.id}')
            if nota_valor and nota_valor.strip():
                try:
                    nota.nota = float(nota_valor)
                    nota.save()
                except ValueError:
                    messages.error(request, f'Valor de nota inválido para {alumno}')
                    return redirect('registro_asistencia_nota', pk=clase.pk)
            else:
                nota.nota = None
                nota.save()
        
        # Si se pidió marcar como vista y el usuario tiene permiso
        if guardar_y_marcar and (
            request.user.is_superuser or 
            request.user.groups.filter(name='SecretariaAcademica').exists() or 
            (request.user == clase.profesor and clase.estado != 'vista')
        ):
            clase.estado = 'vista'
            clase.save()
            messages.success(request, 'Clase marcada como vista y registros guardados.')
        else:
            messages.success(request, 'Registros guardados exitosamente.')
        
        return redirect('profesor_clases', profesor_id=clase.profesor.id)