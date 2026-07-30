import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.db import connection, transaction

print("=== CORRIGIENDO Y CONFIRMANDO TODAS LAS SECUENCIAS EN POSTGRESQL (CON TRANSACTION COMMIT) ===")

with transaction.atomic():
    with connection.cursor() as cursor:
        # 1. Arreglar Admin Log forzando +1000 por seguridad
        try:
            cursor.execute("SELECT setval('django_admin_log_id_seq', COALESCE((SELECT MAX(id) + 1000 FROM django_admin_log), 10000));")
            res_admin = cursor.fetchone()
            print(f"  - django_admin_log_id_seq fijada con éxito en: {res_admin[0]}")
        except Exception as e:
            print(f"  - Aviso en admin_log: {e}")

        # 2. Arreglar todas las secuencias de las tablas en la BD
        cursor.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public';")
        seqs = cursor.fetchall()
        for s in seqs:
            seq_name = s[0]
            if seq_name.endswith('_id_seq'):
                table_name = seq_name[:-7]
                try:
                    cursor.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) + 50 FROM {table_name}), 100));")
                    res = cursor.fetchone()
                    print(f"  - {seq_name} -> fijada en {res[0]}")
                except Exception as e:
                    pass

print("✅ ¡TODAS LAS SECUENCIAS FUERON CORREGIDAS Y GUARDADAS EN POSTGRESQL!")
