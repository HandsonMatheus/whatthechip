from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryentry',
            name='brand',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Fabricante'),
        ),
    ]
