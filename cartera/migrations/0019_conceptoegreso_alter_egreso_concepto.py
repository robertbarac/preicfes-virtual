from django.db import migrations, models
import django.db.models.deletion

CONCEPTO_MAP = {
    'nomina_profesores': 'Nómina profesores',
    'nomina_administrativos': 'Nómina administrativos',
    'arriendo': 'Arriendo',
    'nomina_vendedoras': 'Nómina vendedoras',
    'nomina_auxiliares': 'Nómina auxiliares',
    'servicios_publicos': 'Servicios públicos',
    'servicio_tecnico_pc': 'Servicio técnico PC',
    'servicio_tecnico_fotocopias': 'Servicio técnico fotocopias',
    'publicidad': 'Publicidad',
    'arreglo_planta_fisica': 'Arreglo planta física',
    'adquisiciones': 'Adquisiciones',
    'viaticos': 'Viáticos',
    'otros': 'Otros',
}

def migrar_conceptos_hacia_adelante(apps, schema_editor):
    ConceptoEgreso = apps.get_model('cartera', 'ConceptoEgreso')
    Egreso = apps.get_model('cartera', 'Egreso')

    # 1. Crear todos los conceptos base
    conceptos_creados = {}
    for code, nombre in CONCEPTO_MAP.items():
        obj, _ = ConceptoEgreso.objects.get_or_create(nombre=nombre)
        conceptos_creados[code] = obj

    # Concepto por defecto para cualquier valor inesperado
    otros_obj = conceptos_creados.get('otros')
    if not otros_obj:
        otros_obj, _ = ConceptoEgreso.objects.get_or_create(nombre='Otros')

    # 2. Asignar concepto_fk a todos los egresos existentes
    for egreso in Egreso.objects.all():
        val = str(egreso.concepto or '').strip().lower()
        concepto_obj = conceptos_creados.get(val)
        if not concepto_obj:
            clean_name = val.replace('_', ' ').capitalize() if val else 'Otros'
            concepto_obj, _ = ConceptoEgreso.objects.get_or_create(nombre=clean_name)
        egreso.concepto_fk = concepto_obj
        egreso.save(update_fields=['concepto_fk'])

def migrar_conceptos_hacia_atras(apps, schema_editor):
    Egreso = apps.get_model('cartera', 'Egreso')
    for egreso in Egreso.objects.all():
        if egreso.concepto_fk:
            egreso.concepto = egreso.concepto_fk.nombre.lower().replace(' ', '_')
            egreso.save(update_fields=['concepto'])


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0018_cuota_soporte_pago'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConceptoEgreso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre del concepto')),
                ('descripcion', models.TextField(blank=True, null=True, verbose_name='Descripción')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Concepto de egreso',
                'verbose_name_plural': 'Conceptos de egresos',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='egreso',
            name='concepto_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='egresos', to='cartera.conceptoegreso', verbose_name='Concepto'),
        ),
        migrations.RunPython(migrar_conceptos_hacia_adelante, migrar_conceptos_hacia_atras),
        migrations.RemoveField(
            model_name='egreso',
            name='concepto',
        ),
        migrations.RenameField(
            model_name='egreso',
            old_name='concepto_fk',
            new_name='concepto',
        ),
        migrations.AlterField(
            model_name='egreso',
            name='concepto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='egresos', to='cartera.conceptoegreso', verbose_name='Concepto'),
        ),
    ]
