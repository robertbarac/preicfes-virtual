import os
import sys
import django

sys.path.append('/home/robertbarac/vya/previrtual')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'previrtual.settings')
django.setup()

from django.template import loader

try:
    t = loader.get_template('cartera/informe_diario.html')
    print("✅ Plantilla cartera/informe_diario.html compilada y cargada con éxito (humanize funcionando)!")
except Exception as e:
    print(f"❌ Error al cargar plantilla: {e}")
