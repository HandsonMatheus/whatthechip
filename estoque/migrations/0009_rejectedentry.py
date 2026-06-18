from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('estoque', '0008_alter_pendingentry_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='RejectedEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part_number', models.CharField(db_index=True, max_length=100, verbose_name='Part Number')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantidade')),
                ('chip_type', models.CharField(blank=True, default='', max_length=50, verbose_name='Tipo')),
                ('brand', models.CharField(blank=True, default='', max_length=100, verbose_name='Fabricante')),
                ('capacity', models.CharField(blank=True, default='', max_length=100, verbose_name='Capacidade')),
                ('emcp_ram', models.CharField(blank=True, default='', max_length=100, verbose_name='RAM (eMCP)')),
                ('emcp_nand', models.CharField(blank=True, default='', max_length=100, verbose_name='NAND (eMCP)')),
                ('is_emcp', models.BooleanField(default=False, verbose_name='É eMCP/uMCP')),
                ('interface', models.CharField(blank=True, default='', max_length=100, verbose_name='Interface')),
                ('classification_source', models.CharField(blank=True, default='', max_length=50, verbose_name='Fonte')),
                ('confidence', models.CharField(blank=True, default='', max_length=20, verbose_name='Confiança')),
                ('rejection_reason', models.CharField(default='NÃO RENTÁVEL', max_length=100, verbose_name='Razão')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Reprovado em')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rejected', to='estoque.lot', verbose_name='Lote')),
                ('operator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rejected_entries', to=settings.AUTH_USER_MODEL, verbose_name='Operador')),
            ],
            options={
                'verbose_name': 'Reprovado',
                'verbose_name_plural': 'Reprovados',
                'ordering': ['-created_at'],
            },
        ),
    ]
