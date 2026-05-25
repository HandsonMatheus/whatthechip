from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0002_inventoryentry_brand'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='Número')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='Descrição')),
                ('status', models.CharField(choices=[('open', 'Aberto'), ('closed', 'Fechado')], default='open', max_length=10, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Aberto em')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='Fechado em')),
                ('operator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to=settings.AUTH_USER_MODEL, verbose_name='Operador')),
            ],
            options={
                'verbose_name': 'Lote',
                'verbose_name_plural': 'Lotes',
                'ordering': ['-number'],
            },
        ),
        migrations.AddField(
            model_name='inventoryentry',
            name='lot',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='estoque.lot', verbose_name='Lote'),
        ),
    ]
