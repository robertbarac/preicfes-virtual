import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.db import connection

print("=== RESETEANDO TODAS LAS SECUENCIAS DE LA BASE DE DATOS POSTGRESQL ===")

with connection.cursor() as cursor:
    # Obtener todas las tablas que tienen secuencias auto-incrementales
    sql_get_seqs = """
    SELECT 'SELECT setval(' || quote_literal(pg_get_serial_sequence(quote_ident(table_name), quote_ident(column_name))) || ', COALESCE(max(' || quote_ident(column_name) || '), 1)) FROM ' || quote_ident(table_name) || ';'
    FROM information_schema.columns
    WHERE table_schema='public' AND column_default LIKE 'nextval%';
    """
    cursor.execute(sql_get_seqs)
    queries = [row[0] for row in cursor.fetchall() if row[0]]
    
    count = 0
    for query in queries:
        try:
            cursor.execute(query)
            count += 1
        except Exception as e:
            pass

print(f"✅ ¡{count} secuencias de PostgreSQL (incluyendo django_admin_log) reseteadas exitosamente!")
