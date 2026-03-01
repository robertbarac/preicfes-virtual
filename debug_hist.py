from curriculo.models import HistorialCambios
print("=== Últimos Historiales ===")
hs = HistorialCambios.objects.all().order_by('-id')[:5]
for h in hs:
    print(f"ID: {h.id}")
    print(f"Objeto ID: {h.object_id}")
    print(f"Acción: {h.accion}")
    print("-" * 30)
