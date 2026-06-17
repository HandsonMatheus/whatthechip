from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('estoque', '0006_alter_inventoryentry_classification_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
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
                ('nearest_confirmed', models.CharField(blank=True, default='', max_length=100, verbose_name='Provável typo de')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Tentado em')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending', to='estoque.lot', verbose_name='Lote')),
                ('operator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_entries', to=settings.AUTH_USER_MODEL, verbose_name='Operador')),
            ],
            options={
                'verbose_name': 'Pendente de Conferência',
                'verbose_name_plural': 'Pendentes de Conferência',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='pendingentry',
            constraint=models.UniqueConstraint(fields=('lot', 'part_number'), name='unique_pending_lot_pn'),
        ),
    ]
