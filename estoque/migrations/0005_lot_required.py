from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0004_lot_seed'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='inventoryentry',
            name='unique_operator_pn',
        ),
        migrations.AlterField(
            model_name='inventoryentry',
            name='lot',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='entries',
                to='estoque.lot',
                verbose_name='Lote',
            ),
        ),
        migrations.RemoveField(
            model_name='inventoryentry',
            name='operator',
        ),
        migrations.AddConstraint(
            model_name='inventoryentry',
            constraint=models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_lot_pn',
            ),
        ),
    ]
