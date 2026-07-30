import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.db import connection

print("=== RESETEANDO SECUENCIAS DE CLAVE PRIMARIA EN POSTGRESQL ===")
tables = [
    'usuarios_user', 'suscripciones_subscription', 'academico_alumno',
    'academico_clase', 'evaluaciones_taller', 'evaluaciones_intentotaller',
    'cartera_cuota', 'ventas_preventa', 'ubicaciones_salon'
]

with connection.cursor() as cursor:
    for table in tables:
        try:
            sql = f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(max(id), 1)) FROM {table};"
            cursor.execute(sql)
            print(f"  - Secuencia reseteada para tabla: {table}")
        except Exception as e:
            print(f"  - Aviso en {table}: {e}")

print("✅ ¡Secuencias de PostgreSQL reseteadas exitosamente!")
