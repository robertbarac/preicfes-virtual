import os
import sys
import django

# Configuración de entorno de Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.core.serializers import deserialize
from django.db import models, transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission
from academico.models import Alumno
from usuarios.models import User


def sanitizar_campos_usuario(target_pk, field_dict):
    """Evita violaciones de restricciones únicas de email, username y numero_documento"""
    if 'email' in field_dict:
        if field_dict['email'] == "":
            field_dict['email'] = None
        elif field_dict['email'] and User.objects.filter(email=field_dict['email']).exclude(pk=target_pk).exists():
            field_dict.pop('email')
            
    if 'username' in field_dict and field_dict['username']:
        if User.objects.filter(username=field_dict['username']).exclude(pk=target_pk).exists():
            field_dict.pop('username')

    if 'numero_documento' in field_dict:
        if field_dict['numero_documento'] == "":
            field_dict['numero_documento'] = None
        elif field_dict['numero_documento'] and User.objects.filter(numero_documento=field_dict['numero_documento']).exclude(pk=target_pk).exists():
            field_dict.pop('numero_documento')


def guardar_o_actualizar_objeto(obj):
    ModelClass = obj.__class__
    
    # 1. Si el objeto ya existe por su clave primaria (PK)
    if obj.pk and ModelClass.objects.filter(pk=obj.pk).exists():
        field_dict = {}
        for f in obj._meta.fields:
            if f.attname not in ['id', 'pk']:
                try:
                    field_dict[f.attname] = getattr(obj, f.attname)
                except Exception:
                    pass

        if ModelClass == User:
            sanitizar_campos_usuario(obj.pk, field_dict)

        if field_dict:
            try:
                ModelClass.objects.filter(pk=obj.pk).update(**field_dict)
                return "actualizado"
            except Exception:
                pass
        else:
            return "actualizado"

    # 2. Si es un User y existe por username, numero_documento o email
    if ModelClass == User:
        existente = None
        if getattr(obj, 'username', None):
            existente = User.objects.filter(username=obj.username).first()
        if not existente and getattr(obj, 'numero_documento', None):
            existente = User.objects.filter(numero_documento=obj.numero_documento).first()
        if not existente and getattr(obj, 'email', None):
            existente = User.objects.filter(email=obj.email).first()

        if existente:
            field_dict = {}
            for f in obj._meta.fields:
                if f.attname not in ['id', 'pk']:
                    try:
                        field_dict[f.attname] = getattr(obj, f.attname)
                    except Exception:
                        pass

            sanitizar_campos_usuario(existente.pk, field_dict)

            if field_dict:
                try:
                    User.objects.filter(pk=existente.pk).update(**field_dict)
                    return "actualizado"
                except Exception:
                    pass
            else:
                return "actualizado"

    # 3. Si es un nuevo registro
    try:
        models.Model.save_base(obj, raw=True)
        return "nuevo"
    except Exception:
        try:
            with transaction.atomic():
                obj.save()
            return "nuevo"
        except Exception:
            return "error"


def cargar_fixture_seguro(ruta_json):
    if not os.path.exists(ruta_json):
        print(f"❌ El archivo '{ruta_json}' no existe en este directorio.")
        return

    print(f"📦 Procesando '{ruta_json}'...")
    with open(ruta_json, 'r', encoding='utf-8') as f:
        data_json = f.read()

    # Mapeo automático de modelo Usuario (cartera) -> User (previrtual) y cedula -> numero_documento
    if '"model": "usuarios.usuario"' in data_json:
        print("  🔄 Mapeando modelo 'usuarios.usuario' -> 'usuarios.user' y 'cedula' -> 'numero_documento'...")
        data_json = data_json.replace('"model": "usuarios.usuario"', '"model": "usuarios.user"')
        data_json = data_json.replace('"cedula":', '"numero_documento":')

    deserialized_objects = list(deserialize("json", data_json, ignorenonexistent=True))
    
    pendientes = []
    total_nuevos = 0
    total_actualizados = 0

    # Filtrar registros de sistema iniciales
    for item in deserialized_objects:
        obj = item.object
        if isinstance(obj, (ContentType, Permission)):
            continue
        if isinstance(obj, Group):
            Group.objects.get_or_create(name=obj.name)
            continue
        pendientes.append(obj)

    # Iterar hasta procesar los objetos pendientes
    max_iteraciones = 10
    iteracion = 0
    while pendientes and iteracion < max_iteraciones:
        iteracion += 1
        siguiente_pasada = []
        for obj in pendientes:
            resultado = guardar_o_actualizar_objeto(obj)
            if resultado == "nuevo":
                total_nuevos += 1
            elif resultado == "actualizado":
                total_actualizados += 1
            else:
                siguiente_pasada.append(obj)
        
        if len(siguiente_pasada) == len(pendientes):
            break
        pendientes = siguiente_pasada

    print(f"✅ Finalizado '{ruta_json}': {total_nuevos} nuevos insertados, {total_actualizados} sobreescritos/actualizados. Total procesados: {total_nuevos + total_actualizados}.")


def vincular_alumnos_con_usuarios():
    print("\n🔗 Vinculando Alumnos (identificacion) con Cuentas User (numero_documento)...")
    
    # 1. Obtener conjunto de IDs de usuarios que ya están vinculados a algún Alumno
    usuarios_ocupados = set(
        Alumno.objects.filter(usuario__isnull=False).values_list('usuario_id', flat=True)
    )
    
    alumnos = Alumno.objects.filter(usuario__isnull=True)
    vinculados = 0

    for alumno in alumnos:
        if alumno.identificacion:
            ident = str(alumno.identificacion).strip()
            # 2. Buscar usuarios con ese numero_documento que no estén en usuarios_ocupados
            user = User.objects.filter(numero_documento=ident).exclude(id__in=usuarios_ocupados).first()
            if user:
                try:
                    with transaction.atomic():
                        Alumno.objects.filter(pk=alumno.pk).update(usuario=user)
                    usuarios_ocupados.add(user.id)
                    vinculados += 1
                except Exception:
                    pass

    print(f"✅ Se vincularon automáticamente {vinculados} alumnos presenciales con sus cuentas de usuario de la plataforma.")


if __name__ == '__main__':
    archivos = sys.argv[1:] if len(sys.argv) > 1 else ['virtualrespaldo.json', 'respaldo.json']
    for archivo in archivos:
        cargar_fixture_seguro(archivo)
    vincular_alumnos_con_usuarios()
