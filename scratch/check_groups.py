import os
import sys
import django

sys.path.append('/home/robertbarac/vya/previrtual')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from usuarios.models import User

print("=== GRUPOS Y PERMISOS ACTUALES EN LA BASE DE DATOS UNIFICADA ===")
groups = Group.objects.all()

if not groups.exists():
    print("❌ No hay grupos en la base de datos.")
else:
    for g in groups:
        perms = g.permissions.all()
        user_count = g.user_set.count()
        print(f"\n🏷️ Grupo: '{g.name}' (ID: {g.id}) | Usuarios asociados: {user_count} | Permisos asociados: {perms.count()}")
        for p in perms[:10]:
            print(f"   - {p.content_type.app_label}.{p.codename}: {p.name}")
        if perms.count() > 10:
            print(f"   ... ({perms.count() - 10} permisos más)")
