# cartera/management/commands/revisar_cartera_pendientes.py

from django.core.management.base import BaseCommand
from django.db.models import Q
from academico.models import Alumno
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Revisa alumnos activos sin cartera y muestra el desglose por usuario creador para tareas programadas (PythonAnywhere).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('🔍 Iniciando revisión automatizada de cartera pendiente...'))

        alumnos_sin_cartera = Alumno.objects.filter(
            estado='activo'
        ).filter(
            Q(deuda__isnull=True) | Q(deuda__cuotas__isnull=True)
        ).distinct().select_related('grupo_actual', 'municipio')

        total = alumnos_sin_cartera.count()
        self.stdout.write(self.style.WARNING(f'⚠️ Se encontraron {total} alumnos activos sin cartera o sin cuotas.'))

        ct_alumno = ContentType.objects.get_for_model(Alumno)
        object_ids = [str(a.id) for a in alumnos_sin_cartera]

        # 1. LogEntry de creación
        logs_add = LogEntry.objects.filter(
            content_type=ct_alumno,
            action_flag=ADDITION,
            object_id__in=object_ids
        ).select_related('user')
        log_map_add = {l.object_id: l.user.get_full_name().strip() or l.user.username for l in logs_add}

        # 2. LogEntry de edición (fallback)
        logs_any = LogEntry.objects.filter(
            content_type=ct_alumno,
            object_id__in=object_ids
        ).order_by('id').select_related('user')
        log_map_any = {}
        for l in logs_any:
            if l.object_id not in log_map_any:
                log_map_any[l.object_id] = l.user.get_full_name().strip() or l.user.username

        conteo_usuarios = {}
        for a in alumnos_sin_cartera:
            sid = str(a.id)
            if sid in log_map_add:
                creador = log_map_add[sid]
            elif a.vendedor:
                creador = str(a.vendedor)
            elif sid in log_map_any:
                creador = log_map_any[sid]
            else:
                creador = 'Sin Registro (Histórico)'
            conteo_usuarios[creador] = conteo_usuarios.get(creador, 0) + 1

        self.stdout.write(self.style.MIGRATE_LABEL('\n📊 Desglose de Alertas por Usuario Creador:'))
        for usuario, cant in conteo_usuarios.items():
            self.stdout.write(f'  • {usuario}: {cant} alumno(s) pendiente(s)')

        self.stdout.write(self.style.SUCCESS('\n✅ Tarea de revisión finalizada correctamente.'))
