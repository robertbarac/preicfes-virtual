from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from academico.models import Inasistencia, Alumno, Clase
from academico.forms import InasistenciaForm

@login_required
def registrar_o_editar_inasistencia(request, alumno_pk, clase_pk):
    alumno = get_object_or_404(Alumno, pk=alumno_pk)
    clase = get_object_or_404(Clase, pk=clase_pk)
    
    # Intentar obtener la inasistencia existente. Si no existe, get_or_create la creará.
    inasistencia, created = Inasistencia.objects.get_or_create(
        alumno=alumno,
        clase=clase,
        defaults={'registrado_por': request.user}
    )

    if request.method == 'POST':
        form = InasistenciaForm(request.POST, request.FILES, instance=inasistencia)
        if form.is_valid():
            form.save()
            return redirect(reverse('alumno_detail', kwargs={'pk': alumno_pk}))
    else:
        form = InasistenciaForm(instance=inasistencia)

    return render(request, 'academico/inasistencia_form.html', {
        'form': form,
        'alumno': alumno,
        'clase': clase
    })
