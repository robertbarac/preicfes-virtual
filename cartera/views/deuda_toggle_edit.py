from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import permission_required
from cartera.models import Deuda

@permission_required('cartera.change_deuda')
def toggle_edicion_deuda(_request, pk):
    """
    Vista para habilitar o deshabilitar la edición de una deuda.
    Requiere el permiso 'cartera.change_deuda'.
    """
    deuda = get_object_or_404(Deuda, pk=pk)
    
    # Cambiar el estado de edición
    deuda.edicion_habilitada = not deuda.edicion_habilitada
    deuda.save(update_fields=['edicion_habilitada'])
    
    # Redirigir a la página de detalle del alumno
    # Usar la URL directa en lugar del namespace para evitar problemas
    return redirect(f'/academico/alumnos/{deuda.alumno.id}/')
