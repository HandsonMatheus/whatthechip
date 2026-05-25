from django.db import migrations


def seed_lot_zero(apps, schema_editor):
    """Create one Lot per operator with existing entries, numbered from 0."""
    InventoryEntry = apps.get_model('estoque', 'InventoryEntry')
    Lot = apps.get_model('estoque', 'Lot')
    User = apps.get_model('auth', 'User')

    operator_ids = list(
        InventoryEntry.objects.values_list('operator_id', flat=True).distinct()
    )

    counter = 0
    for op_id in operator_ids:
        try:
            user = User.objects.get(pk=op_id)
        except User.DoesNotExist:
            continue

        lot = Lot.objects.create(
            number=counter,
            operator_id=op_id,
            description='Estoque histórico',
            status='open',
        )
        InventoryEntry.objects.filter(operator_id=op_id).update(lot=lot)
        counter += 1


def reverse_seed(apps, schema_editor):
    Lot = apps.get_model('estoque', 'Lot')
    Lot.objects.filter(description='Estoque histórico').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0003_lot'),
    ]

    operations = [
        migrations.RunPython(seed_lot_zero, reverse_seed),
    ]
