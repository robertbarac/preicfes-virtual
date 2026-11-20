from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from academico.models import Alumno, Grupo
from ubicaciones.models import Salon, Sede


def es_usuario_limbo(user):
    return user.username in ('vvgomez', 'claudia2019') or user.is_superuser


def obtener_o_crear_grupo_limbo(sede):
    """Obtiene o crea el grupo LIMBO para una sede sin colisiones de código."""
    grupo_limbo = Grupo.objects.filter(
        codigo__istartswith='LIMBO',
        salon__sede=sede
    ).first()

    if grupo_limbo:
        return grupo_limbo

    # Obtener o crear un salón "Limbo" en la sede (número 999 como convención)
    salon_limbo = Salon.objects.filter(sede=sede, numero=999).first()
    if not salon_limbo:
        salon_limbo = Salon.objects.create(
            sede=sede,
            numero=999,
            capacidad_sillas=999
        )

    # Generar código único (max_length=20)
    base_codigo = f'LIMBO-{sede.nombre[:10].upper().replace(" ", "")}'[:20]
    codigo = base_codigo
    if Grupo.objects.filter(codigo=codigo).exists():
        sufijo = f'-{sede.id}'
        codigo = f'{base_codigo[:20 - len(sufijo)]}{sufijo}'

    return Grupo.objects.create(
        salon=salon_limbo,
        codigo=codigo
    )


@login_required
def mandar_limbo(request, pk):
    if not es_usuario_limbo(request.user):
        messages.error(request, 'No tienes permiso para enviar alumnos al Limbo.')
        return redirect('alumno_detail', pk=pk)

    if request.method != 'POST':
        return redirect('alumno_detail', pk=pk)

    alumno = get_object_or_404(Alumno, pk=pk)

    if alumno.estado == 'limbo':
        messages.info(request, 'El alumno ya se encuentra en el Limbo.')
        return redirect('alumno_detail', pk=pk)

    if not alumno.grupo_actual or not alumno.grupo_actual.salon or not alumno.grupo_actual.salon.sede:
        messages.error(request, 'El alumno no tiene un grupo/sede asignado para determinar su grupo Limbo.')
        return redirect('alumno_detail', pk=pk)

    # Obtener la sede actual del alumno
    sede = alumno.grupo_actual.salon.sede
    grupo_limbo = obtener_o_crear_grupo_limbo(sede)

    alumno.estado = 'limbo'
    alumno.grupo_actual = grupo_limbo
    # Usar update_fields para evitar la validación del método clean()
    alumno.save(update_fields=['estado', 'grupo_actual'])

    messages.success(request, f'El alumno ha sido enviado al Limbo. Grupo asignado: {grupo_limbo.codigo}.')
    return redirect('alumno_detail', pk=alumno.pk)


@login_required
def mandar_grupo_limbo(request, pk):
    """
    Envia a todos los alumnos activos de un grupo al Limbo (asigna estado 'limbo' 
    y los traslada al grupo LIMBO correspondiente a la sede). Solo accesible para Superusuarios.
    """
    if not request.user.is_superuser and not es_usuario_limbo(request.user):
        messages.error(request, 'No tienes permiso para enviar grupos al Limbo.')
        return redirect('grupo_detalle', pk=pk)

    if request.method != 'POST':
        return redirect('grupo_detalle', pk=pk)

    grupo = get_object_or_404(Grupo, pk=pk)

    if grupo.codigo.upper().startswith('LIMBO'):
        messages.warning(request, 'Este grupo ya es un grupo del Limbo.')
        return redirect('grupo_detalle', pk=pk)

    alumnos = Alumno.objects.filter(grupo_actual=grupo).exclude(estado='limbo')
    total = alumnos.count()

    if total == 0:
        messages.info(request, 'No hay alumnos activos en este grupo para enviar al Limbo.')
        return redirect('grupo_detalle', pk=pk)

    sede = grupo.salon.sede
    grupo_limbo = obtener_o_crear_grupo_limbo(sede)

    for alumno in alumnos:
        alumno.estado = 'limbo'
        alumno.grupo_actual = grupo_limbo
        alumno.save(update_fields=['estado', 'grupo_actual'])

    messages.success(
        request, 
        f'¡Éxito! {total} alumno(s) del grupo {grupo.codigo} han sido enviados al Limbo (Grupo asignado: {grupo_limbo.codigo}).'
    )
    return redirect('grupo_detalle', pk=grupo.pk)

