from django.db import migrations


def normalizar_estudiantes_programa_y_grupos(apps, schema_editor):
    User = apps.get_model('usuarios', 'User')
    Group = apps.get_model('auth', 'Group')
    Programa = apps.get_model('curriculo', 'Programa')
    Alumno = apps.get_model('academico', 'Alumno')

    preicfes = (
        Programa.objects.filter(slug='preicfes', activo=True).first()
        or Programa.objects.filter(tipo='preicfes', activo=True).first()
    )

    student_group = Group.objects.filter(name='Student').first()
    virtual_group = Group.objects.filter(name='VirtualStudent').first()

    # 1. Limpiar doble grupo (Student + VirtualStudent) en alumnos presenciales
    if student_group and virtual_group:
        usuarios_doble_grupo = User.objects.filter(
            groups=student_group
        ).filter(
            groups=virtual_group
        )
        for u in usuarios_doble_grupo:
            alumno = Alumno.objects.filter(usuario_id=u.id).first()
            if not alumno and u.numero_documento:
                alumno = Alumno.objects.filter(identificacion__iexact=u.numero_documento).first()
            # Si es alumno presencial (o tiene grupo Student), conservar solo Student
            if not alumno or alumno.tipo_programa != 'preicfes_virtual':
                u.groups.remove(virtual_group)
            else:
                u.groups.remove(student_group)

    # 2. Garantizar que todo estudiante (Student o VirtualStudent) tenga el programa PreICFES asignado
    if preicfes:
        qs_sin_programa = User.objects.filter(
            programa__isnull=True,
            groups__name__in=['Student', 'VirtualStudent']
        ).distinct()
        for u in qs_sin_programa:
            u.programa_id = preicfes.id
            u.save(update_fields=['programa_id'])


def reverso_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('curriculo', '0005_alter_modulo_ciclo'),
        ('academico', '0001_initial'),
        ('usuarios', '0021_user_meta_puntaje_and_more'),
    ]

    operations = [
        migrations.RunPython(normalizar_estudiantes_programa_y_grupos, reverso_noop),
    ]

