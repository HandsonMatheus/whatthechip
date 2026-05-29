from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0008_chipfamily_is_documented'),
    ]

    operations = [
        migrations.AddField(
            model_name='knownpart',
            name='fbga_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text=(
                    'Código FBGA gravado a laser no chip (ex: D9VFC). '
                    'Micron DRAM mobile: padrão D9XXX. NAND: D8XXX. '
                    'Permite lookup direto pelo código que o operador lê na esteira, '
                    'sem precisar digitar o PN completo.'
                ),
                max_length=10,
            ),
        ),
    ]
