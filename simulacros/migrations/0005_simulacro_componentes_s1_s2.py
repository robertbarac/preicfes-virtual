from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulacros', '0004_resultadosimulacro_puntaje_ingles_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulacro',
            name='componentes_s1',
            field=models.JSONField(
                default=list,
                verbose_name='Orden de componentes Sesión 1',
                help_text=(
                    'Lista ordenada de componentes para S1. Ejemplo: '
                    '["matematicas", "lectura", "sociales", "naturales"]. '
                    "Valores válidos: ['ingles', 'lectura', 'matematicas', 'naturales', 'sociales']."
                ),
            ),
        ),
        migrations.AddField(
            model_name='simulacro',
            name='componentes_s2',
            field=models.JSONField(
                default=list,
                verbose_name='Orden de componentes Sesión 2',
                help_text=(
                    'Lista ordenada de componentes para S2. Ejemplo: '
                    '["sociales", "matematicas", "naturales", "ingles"]. '
                    "Valores válidos: ['ingles', 'lectura', 'matematicas', 'naturales', 'sociales']."
                ),
            ),
        ),
    ]
