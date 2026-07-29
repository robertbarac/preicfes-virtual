from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from academico.models import Alumno, Grupo

def es_staff_o_superuser(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(es_staff_o_superuser)
def retirar_alumno(request, pk):
    alumno = get_object_or_404(Alumno, pk=pk, estado='activo')
    # Buscar grupo RETIRADOS del municipio del alumno y sede central
    grupo_retirados = Grupo.objects.filter(codigo='RETIRADOS').first()
    if not grupo_retirados:
        messages.error(request, 'No existe un grupo RETIRADOS para el municipio del alumno.')
        return redirect('alumno_detail', pk=alumno.pk)
    alumno.estado = 'retirado'
    alumno.fecha_retiro = timezone.localtime(timezone.now()).date()
    alumno.grupo_actual = grupo_retirados
    # Usar update_fields para evitar la validación del método clean()
    alumno.save(update_fields=['estado', 'fecha_retiro', 'grupo_actual'])
    messages.success(request, 'El alumno ha sido retirado exitosamente.')
    return redirect('alumno_detail', pk=alumno.pk)
