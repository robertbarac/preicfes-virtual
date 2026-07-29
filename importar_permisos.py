import json
import os
import sys
import django

sys.path.append('/home/robertbarac/vya/previrtual')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.contrib.auth.models import Group, Permission

json_path = '/home/robertbarac/vya/previrtual/grupos_y_permisos.json'

if not os.path.exists(json_path):
    print(f"⚠️ El archivo '{json_path}' no existe. Asegúrate de haberlo exportado primero.")
    sys.exit(1)

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== IMPORTANDO PERMISOS CON REEMPLAZO AUTOMÁTICO (usuario -> user) ===")

for item in data:
    g_name = item['name']
    group, _ = Group.objects.get_or_create(name=g_name)
    count = 0
    for app_label, codename in item['permissions']:
        # Reemplazo automático de 'usuario' por 'user'
        if 'usuario' in codename:
            codename_original = codename
            codename = codename.replace('usuario', 'user')
            print(f"   🔄 Reemplazando codename: '{codename_original}' -> '{codename}'")
            
        try:
            perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            group.permissions.add(perm)
            count += 1
        except Permission.DoesNotExist:
            print(f"   ⚠️ Permiso no encontrado: {app_label}.{codename}")
            
    print(f"✅ Grupo '{g_name}': {count} permisos importados/vinculados.")

print("\n🎉 Importación y reemplazo completados sin problemas!")
