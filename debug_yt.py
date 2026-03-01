from contenidos.models import BloqueContenido

print("=== Últimos Bloques de YouTube ===")
bloques = BloqueContenido.objects.filter(tipo='youtube').order_by('-id')[:3]
for b in bloques:
    print(f"ID: {b.id}")
    print(f"URL Original: {b.url}")
    print(f"URL Embed Obtenida: {b.youtube_embed_url}")
    print("-" * 30)
