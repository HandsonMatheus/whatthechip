from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0003_chipfamily_pn_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorrectionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('part_number',          models.TextField(db_index=True)),
                ('reported_chip_type',   models.TextField(blank=True, default='',
                    help_text='Tipo exibido no momento do reporte (pode estar errado)')),
                ('reported_capacity',    models.TextField(blank=True, default='',
                    help_text='Capacidade exibida no momento do reporte')),
                ('notes',                models.TextField(blank=True, default='',
                    help_text='Observação livre (preenchida pelo operador no admin)')),
                ('status',               models.CharField(
                    choices=[('pending', '⏳ Pendente'), ('fixed', '✅ Corrigido'),
                             ('rejected', '✗ Rejeitado')],
                    default='pending', max_length=20, db_index=True)),
                ('reported_at',          models.DateTimeField(auto_now_add=True)),
                ('resolved_at',          models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Solicitação de Correção',
                'verbose_name_plural': 'Solicitações de Correção',
                'ordering': ['-reported_at'],
            },
        ),
    ]
